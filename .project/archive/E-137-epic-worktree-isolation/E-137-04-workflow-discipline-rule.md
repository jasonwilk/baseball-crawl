# E-137-04: Update Workflow-Discipline Rule

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the workflow-discipline rule (`.claude/rules/workflow-discipline.md`) reflects the epic worktree model in its closure sequence description and merge-back mechanics.

## Context
The workflow-discipline rule describes the dispatch workflow at a high level, including the closure sequence and the main session's role. It references `git add -A && git commit` for the closure commit. This changes with E-137-01. Note: the SHOULD FIX triage behavior lives in the implement skill (E-137-01's scope), not in workflow-discipline — this rule does not contain triage details.

## Acceptance Criteria
- [ ] **AC-1**: The Workflow Routing Rule section references the closure merge sequence (epic worktree → main, per TN-4) instead of `git add -A && git commit`.
- [ ] **AC-2**: The main session's permitted file operations list includes epic worktree creation and management (`git worktree add/remove` for epic worktrees).

## Technical Approach
Read the updated implement skill (E-137-01) and align the workflow-discipline rule to match. Focus on sections that describe the closure sequence and triage behavior.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/rules/workflow-discipline.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rule is consistent with the updated implement skill
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Light story. Workflow-discipline is a reference document — keep it aligned with the authoritative implement skill.
