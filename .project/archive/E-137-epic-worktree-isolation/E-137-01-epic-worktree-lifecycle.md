# E-137-01: Epic Worktree Lifecycle + Triage Simplification

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill creates an epic-level git worktree at dispatch start, routes all story merge-back patches to it instead of the main checkout, and merges the epic worktree to main at closure. The review finding triage model is simplified: all real findings are fixed, only false positives are dismissed.

This is the foundational story — it rewrites the core dispatch mechanics in the implement skill. All other stories in this epic update dependent files to match the new behavior.

## Context
The implement skill (`.claude/skills/implement/SKILL.md`) currently uses the main checkout (`/workspaces/baseball-crawl`) as the merge-back target for story patches (Phase 3 Step 5a) and runs `git add -A` at closure (Phase 5 Step 10). This structurally captures all working tree contents — not just the current epic's changes. The epic worktree isolates the accumulation point.

The triage model in Phase 3 Step 5 currently has a user-interactive dismiss track for SHOULD FIX items. User feedback: "if you see something real, you don't want to fix it?" — all real findings should be fixed.

## Acceptance Criteria
- [ ] **AC-1**: Phase 2 creates an epic worktree per TN-2 conventions before team creation begins. The epic worktree path is stored and passed to PM and code-reviewer spawn context per TN-8.
- [ ] **AC-2**: Phase 3 Step 5a applies story patches to the epic worktree per TN-3, not to the main checkout. The `cd /workspaces/baseball-crawl && git apply` command is replaced with `cd <epic-worktree> && git apply`.
- [ ] **AC-3**: Phase 3 Step 5a stages applied patches in the epic worktree after successful apply (`git add -A` in epic worktree).
- [ ] **AC-4**: Phase 5 Step 10 uses the closure merge sequence per TN-4 (generate epic patch → dry-run → apply in main → PII scan → user approval → commit → cleanup) instead of `git add -A` in main checkout.
- [ ] **AC-5**: Phase 5 Step 10 handles merge conflicts per TN-4: if dry-run fails, present conflict report with affected files and options to the user.
- [ ] **AC-6**: Phase 5 Step 1 worktree verification checks for orphaned STORY worktrees (existing behavior) but does NOT remove the epic worktree (it is cleaned up in Step 10 after commit).
- [ ] **AC-7**: Phase 3 Step 5 triage is simplified per TN-6: all valid findings (MUST FIX and SHOULD FIX) are routed to the implementer regardless of size or cosmetic nature. Invalid findings (false positives, misunderstandings, findings about untouched code) are dismissed with explanation. The "correct but not worth fixing" dismiss category and the user-interactive dismiss confirmation are removed.
- [ ] **AC-8**: Anti-pattern list updated: add "Do not apply story patches to the main checkout" and "Do not dismiss valid findings based on size or cosmetic nature."
- [ ] **AC-9**: The Workflow Summary diagram at the end of the skill reflects the new epic worktree lifecycle and simplified triage.
- [ ] **AC-10**: Migration merge-time scan per TN-7: at closure, if the epic patch contains migration files and main has new migrations since the epic worktree branched, flag the potential numbering conflict to the user.

## Technical Approach
The implement skill is the single authoritative source for dispatch procedures. This story rewrites three sections: Phase 2 (add epic worktree creation), Phase 3 Step 5a (change merge-back target), and Phase 5 Step 10 (replace `git add -A` with closure merge sequence). The triage simplification touches Phase 3 Step 5 (eliminate "correct but not worth fixing" dismiss category, remove user-interactive dismiss confirmation, preserve invalid-finding dismissals).

Reference TN-1 through TN-8 for all conventions, sequences, and constraints. The Workflow Summary diagram and Anti-Patterns section must be updated to reflect all changes.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-137-02, E-137-03, E-137-04, E-137-05, E-137-06, E-137-07, E-137-08

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-137-02 through E-137-08**: The updated implement skill with epic worktree conventions, triage model, and closure sequence. All downstream stories align their files to match the new behavior described in the updated skill.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing skill structure
- [ ] Code follows project style (see CLAUDE.md)

## Notes
This is the heaviest story in the epic. It touches the most complex file and introduces the most behavioral changes. All other stories are lightweight alignment updates.
