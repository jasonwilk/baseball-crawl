# E-137-02: Update Dispatch-Pattern Rule

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the dispatch-pattern rule (`.claude/rules/dispatch-pattern.md`) reflects the epic worktree model: merge-back targets the epic worktree, the main session's permitted git operations include epic worktree creation/management, and the "Domain Work During Dispatch" section accounts for the epic worktree as a new path.

## Context
The dispatch-pattern rule provides a brief overview of dispatch roles and the main session's permitted operations. It currently describes merge-back as targeting the main checkout and lists the main session's git operations. Both must be updated to reflect the epic worktree model introduced in E-137-01.

## Acceptance Criteria
- [ ] **AC-1**: The "Main session (spawner + router)" role description includes epic worktree creation (`git worktree add`), epic worktree cleanup (`git worktree remove`, `git branch -D`), and patch-apply to the epic worktree as permitted operations.
- [ ] **AC-2**: The merge-back description references the epic worktree (not the main checkout) as the patch-apply target.
- [ ] **AC-3**: The "Domain Work During Dispatch" section lists epic-worktree git commands (creation, patch-apply, cleanup) under "Permitted orchestration."
- [ ] **AC-4**: The closure description references the closure merge sequence (epic worktree → main) per TN-4 instead of `git add -A && git commit`.

## Technical Approach
Read the updated implement skill (E-137-01) and align the dispatch-pattern rule to match. This is a consistency update — the implement skill is authoritative, the rule is a brief overview.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/rules/dispatch-pattern.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rule is consistent with the updated implement skill
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Light story — the dispatch-pattern rule is a brief overview, not the authoritative source. Keep changes minimal and aligned.
