# E-137-06: Update PM Agent Definition

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the product-manager agent definition (`.claude/agents/product-manager.md`) reflects the epic worktree model in any references to dispatch mechanics, closure sequences, or the triage model.

## Context
The PM agent definition describes the PM's role during dispatch (status management, AC verification). It may reference the closure sequence and triage behavior. These need to align with the changes in E-137-01.

## Acceptance Criteria
- [ ] **AC-1**: Read the PM agent definition and audit all sections for references to closure mechanics, merge-back, triage behavior, or the main session's commit process.
- [ ] **AC-2**: For each reference found: update it to reflect the epic worktree model (TN-4 for closure, TN-6 for triage). If no references are found (the PM definition defers to the implement skill), record "No closure/triage references found — PM definition defers to implement skill" in the story's Notes section and skip AC-3.
- [ ] **AC-3**: If the PM agent definition describes the PM's spawn context or dispatch role: add a note that the PM receives the epic worktree path per TN-8 for AC verification context. If the PM definition does not describe spawn context details, skip this AC (the implement skill is authoritative for spawn context).

## Technical Approach
Read the PM agent definition and identify any sections that reference dispatch mechanics, closure, or triage. Cross-reference with the updated implement skill (E-137-01). Update only what is directly referenced — do not add new content the PM definition doesn't already cover.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/agents/product-manager.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Agent definition is consistent with the updated implement skill
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Light story. May result in minimal or no changes if the PM agent definition properly defers to the implement skill for dispatch procedures. AC-4 provides an explicit path for that outcome.
