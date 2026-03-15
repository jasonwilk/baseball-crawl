# E-111-01: Add Archive Verification Gate to Closure Sequence

## Epic
[E-111: Closure Archive Verification Gate](epic.md)

## Status
`DONE`

## Description
After this story is complete, the closure sequence in both `dispatch-pattern.md` and `implement/SKILL.md` will include a verification gate after the archive move step. The gate ensures that both the new files in `/.project/archive/` and the deletions from `/epics/` are staged before proceeding. A main session following the closure sequence will no longer be able to silently leave unstaged archive-related changes in the working tree.

## Context
During E-109 closure, `mv` moved the epic directory to the archive but only the new files were committed -- the source deletions were never staged. The same pattern occurred with E-108. The root cause is that the archive step has no verification, and the commit step happens much later (after team teardown). This story adds the missing verification gate.

## Acceptance Criteria
- [ ] **AC-1**: `/.claude/rules/dispatch-pattern.md` step 13 (archive the epic) includes a verification substep that confirms both the archive destination files and the source directory deletions are staged, per Technical Notes "Fix Approach" section.
- [ ] **AC-2**: `/.claude/skills/implement/SKILL.md` Phase 5 Step 4 (archive the epic) includes the same verification gate, consistent with dispatch-pattern.md per Technical Notes "Consistency Requirement" section.
- [ ] **AC-3**: The implement SKILL.md Workflow Summary diagram reflects the verification gate (e.g., the "Archive epic" line mentions verification).
- [ ] **AC-4**: Both files' archive steps make clear that the main session must not proceed past the archive step with unstaged epic-related changes in the working tree.

## Technical Approach
The two target files both describe the closure archive step but from different perspectives. The implementing agent should read both current archive steps, determine the right mechanism for verification (the Technical Notes describe the contract but not the implementation), and apply the gate consistently to both files. The Workflow Summary in SKILL.md is a text diagram that should also reflect the addition.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `/.claude/rules/dispatch-pattern.md`
- `/.claude/skills/implement/SKILL.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing context-layer content
- [ ] Code follows project style (see CLAUDE.md)

## Notes
This is a context-layer-only story (two `.claude/` files). Per dispatch-pattern.md routing rules, it runs in the main checkout without worktree isolation.
