# E-024: Epic Archive Enforcement

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Completed and abandoned epics must be moved from `/epics/` to `/.project/archive/` immediately upon status change, but this is currently enforced only by prose instructions that can be missed. E-022 was completed but lingered unarchived in `/epics/` until a human noticed. This epic adds both a protocol fix (explicit archive checklist in the PM definition) and technical enforcement (a PreToolUse hook that blocks commits when stale epics remain).

## Background & Context
E-022 (Safety Scan Hardening) was marked COMPLETED but never archived to `/.project/archive/`. The user discovered this manually. The root cause is a process gap: the PM agent definition mentions archiving in the "How Work Flows" section (step 5) but does not include it as an explicit checklist item in the Atomic Status Update Protocol or the Dispatch Procedure close step. Additionally, there is no technical enforcement -- no hook, rule, or script that catches the inconsistency.

The project already has precedent for two-layer enforcement: E-019 (Pre-Commit Safety Gates) and E-022 (Safety Scan Hardening) established the pattern of prose instructions backed by PreToolUse hooks. This epic applies the same pattern to epic archival.

**Expert consultation**: claude-architect domain (hooks, rules, agent definition changes). Consultation was performed during planning. The approach mirrors the established PII hook pattern: a lightweight bash script in `.claude/hooks/` configured as a PreToolUse hook on `Bash` tool calls, scanning for `git commit` commands and checking filesystem state before allowing the commit.

## Goals
- Completed and abandoned epics cannot linger in `/epics/` across commits
- The PM agent has an explicit, checklistable archive step that cannot be skipped through oversight
- The enforcement mechanism is lightweight and follows established project patterns

## Non-Goals
- Automating the archive move itself (the PM or implementing agent still does the `mv` conceptually via Write/Edit -- this epic enforces the check, not the action)
- Changing the archive directory structure or naming conventions
- Adding any monitoring, dashboards, or external alerting

## Success Criteria
- A `git commit` that includes an epic.md file in `/epics/` with status COMPLETED or ABANDONED is blocked by the PreToolUse hook
- The PM agent definition contains explicit archive steps in the Atomic Status Update Protocol
- A `.claude/rules/` rule fires on epic file changes, reminding agents of the archive requirement

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-024-01 | PM Protocol and Rule: Explicit Archive Checklist | DONE | None | claude-architect |
| E-024-02 | PreToolUse Hook: Block Commits with Unarchived Completed Epics | DONE | None | claude-architect |

## Technical Notes

### Hook Design
The hook follows the same pattern as `.claude/hooks/pii-check.sh`:
- Fires on all `Bash` tool calls via PreToolUse
- Checks if the command is `git commit` (same regex: `(^|[;&|]\s*)git\s+commit`)
- If git commit: scans all `epics/*/epic.md` files for status `COMPLETED` or `ABANDONED`
- If any found: outputs JSON denial with the list of epics that need archiving
- If none found: exits silently (allow)
- Requires `jq` for JSON output; fails open if `jq` not available
- Timeout: 10 seconds (same as PII hook)

### Status Detection
Epic status is on a line matching the pattern `` `COMPLETED` `` or `` `ABANDONED` `` (backtick-wrapped, on its own line or after `## Status`). The hook should grep for this pattern in epic.md files under `/epics/`.

A simple approach: `grep -l '`COMPLETED`\|`ABANDONED`' "$CLAUDE_PROJECT_DIR"/epics/*/epic.md 2>/dev/null`

### PM Agent Definition Changes
Three locations in `.claude/agents/product-manager.md` need updates:
1. **Atomic Status Update Protocol** -- add a new "Completing an epic" checklist (currently missing; only story and spike completion are covered)
2. **Dispatch Procedure step 10** -- strengthen "Close" to include explicit archive step
3. **How Work Flows step 5** -- already says "archive" but add emphasis that this is immediate, not deferred

### Rule
A new rule or addition to the existing `project-management.md` rule that fires on `epics/**` paths, stating that any epic with COMPLETED or ABANDONED status must be archived before the next commit.

### File Inventory
- Story 1 touches: `.claude/agents/product-manager.md`, `.claude/rules/project-management.md`
- Story 2 touches: `.claude/hooks/epic-archive-check.sh` (new), `.claude/settings.json`, `.claude/hooks/README.md`
- No file overlap between stories -- they can execute in parallel.

## Open Questions
None -- scope is clear and bounded.

## History
- 2026-03-02: Created. Motivated by E-022 sitting unarchived in /epics/ after completion.
