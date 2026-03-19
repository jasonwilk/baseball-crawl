# E-137-05: Update Code-Reviewer Agent Definition

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the code-reviewer agent definition (`.claude/agents/code-reviewer.md`) references the epic worktree in its Worktree Review section and describes how to access the epic-level diff for integration reviews (used by E-138).

## Context
The code-reviewer currently reads implementer worktree paths to run `git diff --cached main`. With epic worktrees, the code-reviewer also needs to know the epic worktree path for post-epic integration reviews (introduced in E-138). The spawn context update is in E-137-01; this story updates the agent definition to document the new capability.

## Acceptance Criteria
- [ ] **AC-1**: The Worktree Review section mentions that per-story reviews use the implementer's story worktree path (unchanged behavior).
- [ ] **AC-2**: A new section or note describes the epic worktree path as available context for integration-level reviews (the path is provided in spawn context per TN-8).
- [ ] **AC-3**: The agent definition does NOT prescribe how integration reviews work — it only documents that the epic worktree path is available. Integration review procedures are defined in the implement skill (E-138).

## Technical Approach
Read the updated implement skill (E-137-01) for the code-reviewer spawn context changes. Add a brief note to the agent definition about epic worktree awareness. Keep it minimal — the implement skill is authoritative for review procedures.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/agents/code-reviewer.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Agent definition is consistent with the updated implement skill
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Light story. The code-reviewer agent definition is a reference for the agent's capabilities, not an authoritative procedure source.
