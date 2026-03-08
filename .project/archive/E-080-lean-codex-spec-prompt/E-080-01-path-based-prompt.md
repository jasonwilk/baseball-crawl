# E-080-01: Rewrite codex-prompt-spec to path-based prompt

## Epic
[E-080: Lean Codex Spec Review Prompt](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `codex-prompt-spec` skill will generate a lean prompt that gives Codex file paths instead of embedded file contents. The prompt will contain the epic directory path, the rubric file path, the inlined agent roster table, and clear instructions for Codex to read the files itself and perform the review.

## Context
The current skill reads every `.md` file in the epic directory and the full rubric file, then pastes their contents into the generated prompt. This produces prompts that can be thousands of lines long. Since Codex has full repository access, it can read files by path -- the prompt just needs to tell it where to look. This story simplifies the skill's workflow and prompt template accordingly.

## Acceptance Criteria
- [ ] **AC-1**: The skill no longer reads epic/story file contents. Step 1 resolves the epic directory path and confirms it exists (with `epic.md` present), but does NOT Glob+Read individual files.
- [ ] **AC-2**: The skill no longer reads the rubric file contents. Step 2 confirms the rubric file exists at `/.project/codex-spec-review.md`, but does NOT Read its contents.
- [ ] **AC-3**: The generated prompt template includes the epic directory path and rubric file path as absolute paths (e.g., `/workspaces/baseball-crawl/epics/E-080-lean-codex-spec-prompt/`), and instructs Codex to read those files itself. No file contents are embedded in the prompt (except the agent roster table).
- [ ] **AC-4**: The generated prompt instructs Codex to: (a) read the rubric at the given path, (b) read all `.md` files in the given epic directory, (c) review the planning artifacts against the rubric, (d) cite story IDs and AC labels for findings, and (e) recommend a triage team from the agent roster.
- [ ] **AC-5**: The agent roster table remains inlined in the prompt (unchanged from current behavior).
- [ ] **AC-6**: The Purpose section, Workflow Summary, and Edge Cases sections are updated to reflect the new path-based approach (no references to reading/embedding file contents remain).
- [ ] **AC-7**: The "Stories referencing external documents" edge case is rewritten for the path-based approach. The new text clarifies that the prompt scopes Codex to the epic directory and rubric path -- if stories reference external documents critical for review, the user may need to add those paths to the prompt manually.
- [ ] **AC-8**: Anti-pattern 3 is reworded to clarify it applies to the skill definition file itself (not the generated prompt). The reworded text should convey: "Do not embed rubric content or planning artifact content in this skill file. The skill resolves paths and confirms existence; it does not read or cache file contents."
- [ ] **AC-9**: Anti-pattern 4 ("Do not auto-include external referenced documents") is reworded for the path-based approach. The new text should convey: keep the prompt's file-read scope to the epic directory and rubric path -- do not add extra paths for externally referenced documents.
- [ ] **AC-10**: The generated prompt (excluding the fenced code block delimiters used for copy-paste presentation) is under 50 lines.

## Technical Approach
The skill file at `.claude/skills/codex-prompt-spec/SKILL.md` needs its workflow steps and prompt template rewritten. The Prerequisites section stays mostly the same (still need to resolve the epic directory and confirm files exist). The Workflow steps change: Step 1 becomes "resolve epic directory path" (no Glob+Read), Step 2 becomes "confirm rubric exists" (no Read), Step 3 stays the same (roster verification), Step 4 assembles a lean prompt with paths and instructions instead of embedded content. The Edge Cases section needs updates to remove references to embedded content.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/codex-prompt-spec/SKILL.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The `codex-prompt-code` skill is NOT in scope -- diffs must be embedded since they are not files on disk.
- The rubric file path should use the absolute path `/workspaces/baseball-crawl/.project/codex-spec-review.md` in the prompt so Codex can load it unambiguously.
