# E-035: Context Layer Staleness Fixes

## Status
`COMPLETED`

## Overview
Fix actively misleading (P1), stale (P2), and redundant (P3) content across the context layer -- agent definitions, memory files, skills, hooks, and rules. These issues were identified by the claude-architect's comprehensive context layer review on 2026-03-03 and cause agents to operate with incorrect budget estimates, wrong agent counts, stale deployment details, and duplicated CLAUDE.md content.

## Background & Context
The claude-architect conducted a full audit of the context layer (`/.project/research/context-layer-review-2026-03-03.md`) covering all 40+ context-layer files (~4,145 lines). The review identified four priority tiers of issues. P1 findings are actively misleading -- agents making decisions based on these will get wrong answers. P2 findings are stale but not harmful. P3 findings are redundancy violations (memory files duplicating CLAUDE.md). P4 findings are structural observations deferred for future consideration.

PM MEMORY.md fixes (P1.1 / S2 / S10 / S11) were applied directly by the PM as part of epic creation -- the dispatch-pattern exception allows this. The remaining fixes require claude-architect dispatch.

Expert consultation: The architect's review IS the consultation. Findings are incorporated directly into story ACs.

## Goals
- Eliminate all P1 (actively misleading) content from the context layer
- Fix all P2 (stale references) in hooks, skills, and rules
- Reduce P3 (redundant) content in agent memory files to references rather than copies

## Non-Goals
- P4 structural improvements (scoping dispatch-pattern.md, trimming architect topic files) -- deferred per the review's recommendation
- Merging workflow-discipline.md and project-management.md (P3.3) -- deferred, acceptable overlap
- Updating docs-writer MEMORY.md (P4.3) -- will populate naturally with use
- Any changes to CLAUDE.md itself (no CLAUDE.md staleness was found)

## Success Criteria
- All seven P1+P2+P3 finding categories from the review are resolved
- No agent definition or memory file contains stale deployment details, wrong agent counts, or duplicated CLAUDE.md content
- Context-fundamentals skill budget numbers reflect current reality (~1,000-1,270 lines ambient, not ~600-700)
- Dispatch-pattern agent selection table includes docs-writer
- pii-check.sh comment reflects current reality (scanner exists)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-035-01 | Fix architect agent definition and memory | DONE | None | claude-architect |
| E-035-02 | Update context-fundamentals skill budget numbers | DONE | None | claude-architect |
| E-035-03 | Fix stale references in hooks, skills, and rules | DONE | None | claude-architect |
| E-035-04 | Trim memory file duplication | DONE | None | claude-architect |

## Technical Notes

### Research Artifact
The authoritative source for all findings is `/.project/research/context-layer-review-2026-03-03.md`. Every story references specific finding IDs (P1.x, P2.x, P3.x, S1-S11) from that document.

### File Ownership
All stories in this epic modify context-layer files. Per `/.claude/rules/dispatch-pattern.md` routing precedence, all stories route to `claude-architect`.

No two stories share any files -- all four are fully parallelizable.

### Story-to-File Mapping
| Story | Files Modified |
|-------|---------------|
| E-035-01 | `.claude/agents/claude-architect.md`, `.claude/agent-memory/claude-architect/MEMORY.md` |
| E-035-02 | `.claude/skills/context-fundamentals/SKILL.md` |
| E-035-03 | `.claude/hooks/pii-check.sh`, `.claude/skills/filesystem-context/SKILL.md`, `.claude/rules/dispatch-pattern.md`, `.claude/rules/workflow-discipline.md` |
| E-035-04 | `.claude/agent-memory/general-dev/MEMORY.md`, `.claude/agent-memory/api-scout/MEMORY.md` |

### Current Actual Budget Numbers (for E-035-02)
From the review's Section 6:
| Item | Documented | Actual |
|------|-----------|--------|
| CLAUDE.md | ~232 lines | 297 lines |
| Rules (file count) | 6 files | 10 files |
| Rules (total lines) | ~212 lines | 546 lines |
| Agent definition (range) | ~100-200 lines | 139-327 lines |
| Agent MEMORY.md (range) | Variable | 12-97 lines |
| **Ambient subtotal** | **~600-700 lines** | **~994-1,267 lines** |

### PM MEMORY.md Fixes (Already Applied)
The following fixes from the review were applied directly by the PM during epic creation (dispatch-pattern exception for PM's own memory):
- P1.1 / S1: Removed E-001 from Active Epics (it is COMPLETED and archived)
- S2: Added E-001, E-028, E-034 to the archived parenthetical
- S10: Updated E-005 entry to reflect E-001-02 blocker now cleared
- S11: Fixed architecture line from "src/gamechanger/ for source" to accurate "src/ for source (gamechanger/, api/, http/, safety/)"

## Open Questions
None -- all findings are fully specified in the review artifact.

## History
- 2026-03-03: Created from context-layer-review-2026-03-03.md findings. PM MEMORY.md fixes applied directly. Epic set to READY -- all stories have testable ACs, no expert consultation needed beyond the review itself.
- 2026-03-03: All four stories dispatched in parallel and completed. Summary of changes:
  - E-035-01: Fixed architect agent def ("seven agents", added docs-writer) and architect MEMORY.md (Home Linux server, no Litestream, added docs-writer). Note: docs-writer color is purple (not cyan as story AC suggested).
  - E-035-02: Updated context-fundamentals skill budget from ~600-700 to ~1,000-1,270 lines. Worked example updated (~654 -> ~1,080 ambient, ~1,204 -> ~1,630 total). Task-specific combined total updated to 1,800-2,500.
  - E-035-03: Fixed pii-check.sh comment (removed "E-019-03 pending"), updated filesystem-context E-010 path to archived location, added docs-writer row to dispatch-pattern agent selection table, removed misleading `paths: ["**"]` from workflow-discipline.md frontmatter.
  - E-035-04: Trimmed general-dev MEMORY.md from 87 to 53 lines (-34) and api-scout MEMORY.md from 73 to 67 lines (-6) by replacing duplicated CLAUDE.md/rules content with references.
  - No documentation impact -- all changes are to context-layer files only, not user-facing docs.
  - Epic set to COMPLETED.
