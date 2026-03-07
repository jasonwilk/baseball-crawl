# E-067: Context-Layer Assessment Gate

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add a mandatory "Context-Layer Assessment Gate" to the epic closure sequence. Every epic's closure must evaluate whether the epic produced conventions, boundaries, patterns, or architectural decisions that should be codified in the context layer (CLAUDE.md, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`) before archival. This prevents lessons from becoming ephemeral when epic files are archived.

## Background & Context
This is the second consecutive epic (E-064, following the E-062 pattern) where the user had to ask "did we bake this into the context layer?" and the answer was "no -- it's only in the epic files." Epic files get archived to `/.project/archive/` on completion. Archived files are frozen historical records that agents do not routinely load. Conventions, patterns, and architectural decisions captured only in epic files are effectively lost.

The existing Documentation Assessment Gate (`.claude/rules/documentation.md`) covers user-facing docs (`docs/admin/`, `docs/coaching/`). It does NOT cover the context layer -- the rules, conventions, and agent guidance that shape how agents work. This is a structural gap.

**Expert consultation**: Claude-architect consulted (2026-03-07). Recommended separate rule file (not folded into documentation.md), confirmed 6-trigger checklist, Step 3a position, and Option D assessment model (main session with per-trigger verdicts, spawn architect only when triggers fire). Full assessment in Technical Notes.

## Goals
- Every epic closure includes a mandatory context-layer assessment before archival
- The assessment uses a concrete per-trigger checklist with explicit yes/no verdicts recorded in the epic's History section
- When any trigger fires, claude-architect is spawned to update context-layer files
- The gate is structural (blocks archival) not advisory (suggestion)

## Non-Goals
- Retroactively assessing all archived epics for missed codification
- Changing the existing Documentation Assessment Gate (it covers a different domain)
- Adding overhead to epics that have no context-layer impact (explicit "no" verdicts are fast when no triggers fire)
- Modifying CLAUDE.md (CA confirmed: keep this in rules/skills layer)

## Success Criteria
- A new rule file defines the assessment triggers and procedure
- The closure sequence in all three authoritative files includes the context-layer assessment gate at Step 3a (after documentation assessment, before archive)
- workflow-discipline.md has a parallel gate entry
- The implement skill's anti-patterns list includes "Do not skip the context-layer assessment"
- The gate requires per-trigger verdicts (not a blanket "no impact")
- When triggers fire, claude-architect is dispatched before archival can proceed

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-067-01 | Add context-layer assessment gate to closure sequence | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### CA Assessment (2026-03-07)

**Architecture decision**: Separate rule file (`.claude/rules/context-layer-assessment.md`), NOT folded into `documentation.md`. Three reasons: (1) different ownership (docs-writer vs claude-architect), (2) different glob triggers, (3) different assessment logic ("did something user-facing change?" vs "did we learn something that should change how agents operate?").

**Assessment triggers** (6 total, CA-confirmed):

1. New convention, pattern, or constraint established
2. Architectural decision with ongoing implications
3. Footgun, failure mode, or boundary discovered
4. Change to agent behavior, routing, or coordination
5. Domain knowledge discovered that should influence agent decisions in future epics
6. New CLI command, workflow, or operational procedure introduced

**Position in closure sequence**: Step 3a -- immediately after documentation assessment, before archive. Both gates must pass independently.

**Assessment model**: Option D -- main session performs assessment using a concrete per-trigger checklist with **explicit yes/no verdicts recorded in the epic's History section**. Spawns claude-architect only when a trigger fires. Key insight from CA: the problem wasn't that the main session couldn't evaluate -- it was that no checklist existed at all. Requiring explicit per-trigger verdicts forces the evaluation to actually happen. A blanket "no context-layer impact" is not sufficient.

### Files to Update (CA-confirmed, 6 total)

1. **`.claude/rules/context-layer-assessment.md`** (new) -- the rule file with trigger checklist, assessment procedure, spawn-architect instruction, blocking semantics. Glob-triggered on `epics/**` and `.project/archive/**`.
2. **`/.claude/rules/dispatch-pattern.md`** -- new step between current Steps 13 and 14 in Closure Sequence (renumber subsequent steps)
3. **`/.claude/skills/implement/SKILL.md`** -- new Step 3a in Phase 5 (between documentation assessment and archive)
4. **`/.claude/rules/workflow-discipline.md`** -- new "Context-Layer Assessment Gate" entry parallel to Documentation Assessment Gate
5. **`/.claude/skills/implement/SKILL.md`** -- new anti-pattern: "Do not skip the context-layer assessment"
6. **`/.claude/agents/product-manager.md`** -- new step 3a in "Completing an epic" checklist (between documentation assessment and archive)

Note: CLAUDE.md does NOT need changes (CA confirmed: keep in rules/skills layer).

### Structural Parallel with Documentation Assessment Gate

The documentation gate serves as the exact structural template:

| Aspect | Documentation Gate | Context-Layer Gate |
|--------|-------------------|-------------------|
| Rule file | `.claude/rules/documentation.md` | `.claude/rules/context-layer-assessment.md` |
| Owner | docs-writer | claude-architect |
| Domain | `docs/admin/`, `docs/coaching/` | CLAUDE.md, `.claude/rules/`, `.claude/agents/`, `.claude/skills/` |
| Closure step | Step 3 / Step 13 | Step 3a / Step 13a (new) |
| workflow-discipline.md | "Documentation Assessment Gate" | "Context-Layer Assessment Gate" (new) |
| Blocking | Blocks archival | Blocks archival |
| implement anti-pattern | #5: "Do not skip the documentation assessment" | New #8: "Do not skip the context-layer assessment" |

## Open Questions
- None

## History
- 2026-03-07: Created as DRAFT. Claude-architect consultation escalated to team lead.
- 2026-03-07: CA consultation complete. Separate rule file, 6 triggers, Step 3a position, Option D (per-trigger verdicts). Stories written, epic set to READY.
