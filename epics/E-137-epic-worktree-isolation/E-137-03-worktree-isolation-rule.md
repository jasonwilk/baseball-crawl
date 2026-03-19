# E-137-03: Update Worktree-Isolation Rule

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the worktree-isolation rule (`.claude/rules/worktree-isolation.md`) distinguishes between story-level worktrees (existing) and epic-level worktrees (new). Agents in story worktrees have the same constraints as today. The rule also describes the epic worktree's role and what happens within it.

## Context
The worktree-isolation rule currently describes a single tier of worktree (story-level). With E-137-01, there are now two tiers: story worktrees (where implementers work) and the epic worktree (where story patches accumulate). Agents never work directly in the epic worktree — it is managed by the main session. But the rule should document both tiers for clarity.

## Acceptance Criteria
- [ ] **AC-1**: The rule distinguishes two worktree tiers: story-level (existing, `/tmp/.worktrees/baseball-crawl-*/`) and epic-level (new, `/tmp/.worktrees/baseball-crawl-E-NNN/`).
- [ ] **AC-2**: Story-level worktree constraints are unchanged (no Docker, no credentials, no committing, no branch management).
- [ ] **AC-3**: The rule states that agents do NOT work directly in the epic worktree — it is managed by the main session for patch accumulation and closure merge.
- [ ] **AC-4**: The rule notes that the main checkout path check (`cwd is NOT /workspaces/baseball-crawl`) still correctly identifies story worktrees, since epic worktrees are also outside the main checkout.

## Technical Approach
Read the updated implement skill (E-137-01) for the epic worktree conventions. Add a section to the rule explaining the two-tier model. Existing story-level constraints are unchanged.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/rules/worktree-isolation.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rule is consistent with the updated implement skill
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Light story. The key insight: agents only encounter story worktrees. The epic worktree is infrastructure the main session manages. The rule documents this for completeness.
