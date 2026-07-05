# E-251-01: Implement-skill closure-path repair (F-H5 + abort-path ancillary destruction)

## Epic
[E-251: Dispatch-Machinery Repair](../E-251-dispatch-machinery-repair/epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill's two broken closure-sequence resets work for epics that ADD files. The red-suite recovery reset and the operator-abort reset both use an undo that correctly reverses a patch containing newly-created files, and the abort path no longer destroys the staged-but-uncommitted Step 7a ancillary edits (vision-signals, ideas, AND `.claude/agent-memory/` PM-memory edits). The abort explicitly REVERSES the sub-step-7 PM-memory Active→Archived flip via a surgical PM-driven section-move (PM moves the epic from Archived back to Active in its own MEMORY.md, editing only the sub-step-7 lines) — NOT a whole-file `git checkout -- MEMORY.md`, which would destroy any Step 7a memory edit made to the same file. Leaving the flip in place while the patch is reversed would strand PM memory saying "Archived" against an ACTIVE epic (see AC-2), so the flip is reversed while ALL Step 7a ancillary edits are preserved. The prose describing each reset accurately reflects what it does.

## Context
This is audit finding **F-H5** (HIGH) plus the paired abort-path destruction defect (audit §2 MEDIUM "Implement skill closure resets"). Both live in `.claude/skills/implement/SKILL.md`'s closure sequence and are the same class of bug: a reset built on `git checkout -- .`, which only restores TRACKED files to HEAD and therefore (a) leaves patch-created untracked files behind and (b) reverts legitimately-staged ancillary edits. Per epic TN-2, the audit verified the fix. These defects break closure recovery for any epic that adds a file — which includes E-250 (adds migration 008) — so they must be fixed before dispatch.

## Acceptance Criteria
- [ ] **AC-1**: The red-suite closure reset (audit F-H5, ~sub-step 5 of the closure sequence) no longer relies on `git checkout -- .` to revert the applied patch. It uses a symmetric undo that reverses the patch INCLUDING files the patch created (the audit-verified form is `git apply -R --3way /tmp/E-NNN-epic.patch`), so a subsequent re-apply after remediation does not error on already-present/untracked files. Verifiable outcome: a red-suite closure on an epic that added a new file can reset and re-apply without a deadlock, and the skill text no longer instructs `git checkout -- .` as the patch-revert on this path.
- [ ] **AC-2**: The operator-abort reset (~sub-step 9 reject path (c), "abort") REVERSES all three Step-8 closure actions: (1) the applied patch, via the symmetric `git apply -R --3way` of the saved epic patch (handles patch-created files); (2) the archive rename, via `git mv` back; and (3) the sub-step-7 PM-memory Active→Archived flip, which is a MAIN-ONLY edit OUTSIDE the patch, reversed by a SURGICAL PM-driven section-move (PM moves the epic from Archived back to Active in its own MEMORY.md, editing only the sub-step-7 lines) — NOT a whole-file `git checkout -- MEMORY.md`, which would destroy any Step 7a PM-memory edit made to the same file. The abort preserves ALL Step 7a ancillary edits — vision-signals, ideas, AND `.claude/agent-memory/` (PM memory) edits (they predate Step 8 and are legitimately staged). The sub-step-7 flip MUST NOT survive: leaving it while `git apply -R` flips `epic.md` back to ACTIVE produces an inconsistent state (PM memory says "Archived" while the epic is ACTIVE). Patch-created untracked files are not left orphaned.
- [ ] **AC-3**: The abort-path prose no longer claims the reset restores "the main checkout to its pre-Step 8 state" in a way that is false; it accurately describes the three-action reversal (applied patch, archive rename, and the surgical PM-driven reversal of the sub-step-7 PM-memory flip) and states which edits are preserved (ALL Step 7a ancillary edits — vision-signals, ideas, and PM memory) versus reverted (only the sub-step-7 Active→Archived flip).
- [ ] **AC-4**: The two reset sequences are internally consistent with the rest of the closure sequence (the `git mv` archive-undo step and the staging steps still line up with the corrected reset), and the code-reviewer confirms the reset logic and prose agree with each other and with the surrounding sub-steps. Per epic TN-1, CA locates the current sub-step positions (line numbers may have drifted from the audit's cite).

## Technical Approach
Per epic TN-2. Locate the closure-sequence red-suite reset and the abort-path reset in `.claude/skills/implement/SKILL.md`, replace the `git checkout -- .` patch-revert with the symmetric `git apply -R --3way` undo on the saved epic patch, and rewrite the accompanying prose so the described behavior matches. Preserve every other sub-step (archive-rename undo, staging, PII-scan note). CA owns the exact command sequences and wording; do not change closure policy, only make the reset mechanics correct.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` — correct the red-suite reset (F-H5) and the abort-path reset (ancillary-destruction), and their prose

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The specific fix is quoted here so the story is self-contained: `PLATFORM-AUDIT.md` is uncommitted and may disappear. Audit refs: §2 HIGH F-H5 (`.claude/skills/implement/SKILL.md:558`) and §2 MEDIUM "Implement skill closure resets destroy Step 7a ancillary edits" (`:578`).
