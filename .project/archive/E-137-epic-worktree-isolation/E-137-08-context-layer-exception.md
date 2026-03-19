# E-137-08: Context-Layer Story Exception Documentation

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill clearly documents the context-layer story exception in the epic worktree model: stories that modify only context-layer files run in the main checkout (not the epic worktree), and their changes are committed separately from the epic's atomic commit.

## Context
Per TN-5, context-layer stories stay in the main checkout for immediate visibility. This is existing behavior, but the epic worktree model changes the implications: context-layer story changes are NOT in the epic worktree's diff, NOT in the epic's atomic commit, and must be committed via a separate path. The implement skill needs explicit documentation of this exception and its handling.

## Acceptance Criteria
- [ ] **AC-1**: The implement skill's Phase 3 Step 2 (context-layer routing) explicitly states that context-layer-only stories run in the main checkout and their changes are NOT accumulated in the epic worktree.
- [ ] **AC-2**: The implement skill documents the commit ordering constraint per TN-5: context-layer changes remain UNCOMMITTED in the main checkout throughout dispatch, preserving a stable diff base for all story patches and the epic closure merge. No context-layer commit occurs before the epic's atomic commit.
- [ ] **AC-3**: The implement skill's Phase 5 closure sequence includes a step AFTER the epic's atomic commit to handle uncommitted context-layer changes: check for uncommitted changes in the main checkout, and if found, commit them separately with an appropriate message (e.g., `chore(E-NNN): context-layer updates`). If the epic commit fails or is aborted, context-layer changes remain uncommitted.
- [ ] **AC-4**: The Workflow Summary diagram reflects the context-layer exception path, showing context-layer commit AFTER the epic commit.

## Technical Approach
Read the updated implement skill (E-137-01) and add explicit documentation for the context-layer exception. The exception already exists in the current skill — this story makes it explicit in the context of epic worktrees, where the "separate commit" behavior is a new consequence.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Exception handling is consistent with TN-5
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Light story. The context-layer exception already exists — this story documents it explicitly in the epic worktree context and adds the separate-commit handling.
