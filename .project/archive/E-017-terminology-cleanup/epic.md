# E-017: Product Manager Terminology Cleanup

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Replace stale "Project Manager" prose references with "Product Manager" across live project files. E-016 rewrote the PM agent definition and orchestrator but left behind scattered role-title references in agent memory headings, research artifacts, and decision logs. This cleanup eliminates the inconsistency so all live documentation reflects the PM's actual role.

## Background & Context
E-016 (Evolve PM to Product Manager) was completed and archived. It rewrote the PM agent definition (`product-manager.md`) and the orchestrator, but its own epic notes flagged residual terminology:

> "Post-E-016: context-fundamentals and filesystem-context need a terminology pass (product-manager naming). Capture as IDEA."

That IDEA was never captured. The `context-fundamentals` skill has since been cleaned independently, but other files still carry stale "Project Manager" prose. This epic closes the gap.

**Scope of the problem**: A codebase-wide grep found ~70 files matching `project.manager`. The vast majority are archived epics (out of scope) or agent-name identifiers like `product-manager` (technical identifiers that stay). Only **5 lines across 5 live files** contain the prose role title "Project Manager" or "project manager" that should read "Product Manager" or "product manager".

**No expert consultation required** -- this is a pure terminology/process cleanup within the PM's own domain.

## Goals
- Every live file's prose role references say "Product Manager" (not "Project Manager")
- Agent name identifiers (`product-manager`, file paths, backtick references) remain unchanged

## Non-Goals
- Renaming the agent file `product-manager.md` (already renamed)
- Updating archived epics in `/.project/archive/` (historical record stays as-is)
- Updating file path references like `/.claude/agent-memory/product-manager/MEMORY.md`
- Updating agent-name table entries like `| **product-manager** |`
- Any code changes (no Python files are affected)

## Success Criteria
- A case-insensitive grep for `"Project Manager"` (two words, space-separated) across all non-archived `.md` files returns zero results, excluding:
  - Files under `/.project/archive/`
  - Occurrences that are part of the E-017 epic itself (this file and its story)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-017-01 | Replace stale "Project Manager" prose references | DONE | None | - |

## Technical Notes

### Exact Changes Required

**File 1**: `/.claude/agent-memory/product-manager/MEMORY.md`
- Line 1: `# Project Manager -- Agent Memory` -> `# Product Manager -- Agent Memory`

**File 2**: `/.claude/agent-memory/product-manager/lessons-learned.md`
- Line 1: `# Lessons Learned (Project Manager)` -> `# Lessons Learned (Product Manager)`

**File 3**: `/.project/decisions/E-009-decision.md`
- Line 4: `**Decision Owner**: Project Manager (E-009-01)` -> `**Decision Owner**: Product Manager (E-009-01)`

**File 4**: `/.project/research/E-009-R-01-database-options.md`
- Line 370: `"the project manager's prior"` -> `"the product manager's prior"`

**File 5**: `/.project/research/E-009-R-02-api-layer-options.md`
- Line 551: `"The Project Manager's prior"` -> `"The Product Manager's prior"`

### What NOT to Change
- Any occurrence of `product-manager` (hyphenated) -- this is the agent filename/identifier
- Any file path containing `product-manager` (e.g., `/.claude/agents/product-manager.md`)
- Any backtick-wrapped `product-manager` reference (code/config identifier)
- Any bold agent name like `**product-manager**` in tables (the Name column stays; only Description columns get role-title updates, which were already done in E-016)
- Anything in `/.project/archive/`

## Open Questions
- None. Scope is fully defined.

## History
- 2026-03-01: Created. Scope investigation complete. Marked READY.
