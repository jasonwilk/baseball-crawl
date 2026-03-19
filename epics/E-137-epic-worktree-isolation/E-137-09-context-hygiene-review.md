# E-137-09: Context-Layer Hygiene Review

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`TODO`

## Description
After this story is complete, all context-layer files affected by E-137 have been reviewed for internal consistency using the context-fundamentals skill. Cross-references between the implement skill, dispatch-pattern rule, worktree-isolation rule, workflow-discipline rule, agent definitions, and codex-review skill are verified as aligned.

## Context
E-137 touches 8+ context-layer files across stories 01-08. Each story updates its own file(s) to align with E-137-01's implement skill changes. Story 09 is the integration check: verify that all files tell a consistent story about epic worktrees, triage, and closure mechanics. This catches drift introduced when multiple stories independently update related files.

## Acceptance Criteria
- [ ] **AC-1**: Load the context-fundamentals skill and run a cross-reference audit across all files modified by E-137 stories 01-08.
- [ ] **AC-2**: Every reference to merge-back mechanics across all modified files consistently describes the epic worktree as the target (no residual references to main checkout as merge-back target).
- [ ] **AC-3**: Every reference to the triage model across all modified files consistently describes the simplified model per TN-6 (fix all valid findings regardless of size; dismiss only invalid findings; no "correct but not worth fixing" category; no user-interactive dismiss confirmation).
- [ ] **AC-4**: Every reference to the closure sequence across all modified files consistently describes the epic worktree → main merge (no residual references to `git add -A`).
- [ ] **AC-5**: The epic worktree path convention (`/tmp/.worktrees/baseball-crawl-E-NNN/`) and branch convention (`epic/E-NNN`) are consistent everywhere they appear.
- [ ] **AC-6**: Any inconsistencies found are fixed in-place. Findings and corrections are documented in a hygiene audit log at `/.project/research/E-137-09-hygiene-audit.md`.

## Technical Approach
Use the context-fundamentals skill to identify cross-references between the modified files. Read each file and verify that descriptions of merge-back, triage, closure, and worktree conventions are consistent. Fix any drift in-place.

## Dependencies
- **Blocked by**: E-137-02, E-137-03, E-137-04, E-137-05, E-137-06, E-137-07, E-137-08
- **Blocks**: None

## Files to Create or Modify
- `/.project/research/E-137-09-hygiene-audit.md` (new — audit log documenting findings and corrections)
- `.claude/skills/implement/SKILL.md` (if inconsistencies found)
- `.claude/rules/dispatch-pattern.md` (if inconsistencies found)
- `.claude/rules/worktree-isolation.md` (if inconsistencies found)
- `.claude/rules/workflow-discipline.md` (if inconsistencies found)
- `.claude/agents/code-reviewer.md` (if inconsistencies found)
- `.claude/agents/product-manager.md` (if inconsistencies found)
- `.claude/skills/codex-review/SKILL.md` (if inconsistencies found)
- `scripts/codex-review.sh` (if inconsistencies found)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Cross-reference audit complete with findings documented
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing functionality

## Notes
This is the final wave-3 story. It runs after all other stories are complete and serves as the integration verification gate. If no inconsistencies are found, the story is still DONE — the verification itself is the deliverable.
