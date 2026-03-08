# E-080-04: Rewrite codex-prompt-code rubric embedding to path-based

## Epic
[E-080: Lean Codex Review Prompts](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `codex-prompt-code` skill will reference the code review rubric by path instead of embedding its full contents into the generated prompt. The skill will confirm the rubric file exists but will not read it. The generated prompt will instruct Codex to read the rubric itself. The diff, agent roster, and all other prompt sections remain unchanged.

## Context
The `codex-prompt-code` skill generates a copy-paste code review prompt for Codex. Step 4 currently reads the full rubric file (`.project/codex-review.md`) via Read, and Step 6 embeds its contents into the prompt template. Since Codex has full repository access when the user pastes the prompt (confirmed by E-080-01, which successfully converted the sister `codex-prompt-spec` skill to path-based), the rubric can be referenced by path instead of embedded. The diff content (gathered in Step 2 via git commands) is runtime-generated with no on-disk path and must remain embedded -- this is the key asymmetry with E-080-01 where both rubric and epic contents became path references.

The original E-080 Non-Goals incorrectly excluded this skill, stating "Codex is not executing in-repo." E-080-01 proved otherwise. This story also corrects that Non-Goals entry.

## Acceptance Criteria
- [ ] **AC-1**: Step 4 confirms the rubric file exists at `/workspaces/baseball-crawl/.project/codex-review.md` without reading its contents. If missing, report the error and stop (same behavior as current).
- [ ] **AC-2**: The generated prompt template references the rubric by absolute path and instructs Codex to read it, instead of embedding the full rubric content. The rubric section of the prompt is under 5 lines (path + read instruction).
- [ ] **AC-3**: The generated prompt still embeds the full diff content from Step 2 (runtime-generated, cannot be path-referenced). No changes to Steps 1, 2, 3, or 5.
- [ ] **AC-4**: The Purpose section is updated to say the rubric is referenced by path, not embedded (e.g., "a path reference to the project's code review rubric" instead of "the project's code review rubric"). The word "self-contained" is removed or softened -- the prompt now depends on Codex having repo access to read the rubric.
- [ ] **AC-5**: Prerequisites item 2 no longer says "you will read it in Step 4" -- it says the file must be present (existence check, not read).
- [ ] **AC-6**: Anti-pattern 3 is reworded to prohibit rubric embedding in both the skill file and the generated prompt. New text should convey: "Do not embed rubric content in this skill file or in the generated prompt. The rubric is referenced by absolute path; Codex reads it directly."
- [ ] **AC-7**: The Workflow Summary diagram is updated: Step 4 says "Verify rubric exists" (not "Read rubric").
- [ ] **AC-8**: The epic's Non-Goals section is updated to remove the incorrect exclusion of `codex-prompt-code`. The bullet that says "Changes to the `codex-prompt-code` skill (copy-paste prompt where both diff and rubric must be embedded -- Codex is not executing in-repo)" is removed entirely.
- [ ] **AC-9**: All other steps (1, 2, 3, 5), anti-patterns (1, 2, 4, 5), and edge cases (empty diff, large diff, binary files, no untracked files, rubric missing) are unchanged.

## Technical Approach
The skill file at `.claude/skills/codex-prompt-code/SKILL.md` and the epic file at `epics/E-080-lean-codex-spec-prompt/epic.md` both need modification. The skill changes follow the same pattern established by E-080-01 for the sister spec prompt skill: Step 4 becomes an existence check, the prompt template's rubric section becomes a path reference with a read instruction, and surrounding prose sections are updated to reflect the new approach. The diff embedding, size check, and agent roster are unaffected. The epic Non-Goals update removes one bullet.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/codex-prompt-code/SKILL.md` (modify)
- `epics/E-080-lean-codex-spec-prompt/epic.md` (modify -- Non-Goals section only)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The diff MUST remain embedded in the generated prompt. It is runtime-generated from git commands and has no on-disk path. This is the fundamental asymmetry with E-080-01.
- The size check in Step 3 already runs before the rubric step and already counts only diff content. No changes needed to size check logic or thresholds.
- SE flagged that path-based rubric references in copy-paste prompts assume Codex runs locally against this repo. This assumption was validated by E-080-01 (codex-prompt-spec uses the same copy-paste model and was successfully converted). If the prompt is ever used in a non-local Codex context, this assumption would break -- but that is not the current usage pattern.
