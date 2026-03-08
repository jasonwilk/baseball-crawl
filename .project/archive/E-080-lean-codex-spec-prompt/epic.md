# E-080: Lean Codex Review Prompts

## Status
`COMPLETED`

## Overview
Four review artifacts -- the `codex-prompt-spec` skill (copy-paste spec prompt), the `codex-prompt-code` skill (copy-paste code prompt), the `codex-spec-review.sh` script (in-process spec review), and the `codex-review.sh` script (in-process code review) -- embed file contents into generated prompts that Codex could read by path. This wastes tokens because Codex has full repository access. This epic rewrites all four artifacts to produce lean prompts containing only paths, instructions, and (for the skills) the agent roster. Diffs remain embedded where they must (runtime-generated content not on disk).

## Background & Context
Four artifacts generate review prompts with embedded file contents that Codex could read by path:

1. **`codex-prompt-spec` skill** (`.claude/skills/codex-prompt-spec/SKILL.md`) -- created in E-074. Generates a copy-paste spec review prompt. Reads and embeds full file contents (rubric + all epic/story files).
2. **`codex-prompt-code` skill** (`.claude/skills/codex-prompt-code/SKILL.md`) -- created in E-074. Generates a copy-paste code review prompt. Reads and embeds the full rubric. The diff is runtime-generated and must remain embedded.
3. **`codex-spec-review.sh` script** (`scripts/codex-spec-review.sh`) -- created in E-034. Assembles a spec review prompt and pipes it to `codex exec --ephemeral -`. Also `cat`s the full rubric and all `.md` files into the prompt.
4. **`codex-review.sh` script** (`scripts/codex-review.sh`) -- created in E-034/E-036. Assembles a code review prompt and pipes it to `codex exec --ephemeral -`. Embeds the full rubric via `cat` (line 65). The diff is runtime-generated and must remain embedded, but the rubric is a file on disk.

All four produce prompts that can be thousands of lines. Codex operates in the same repository and can read any file by path. The prompts only need to tell Codex *where* to look and *what* to do -- not paste file contents inline.

No domain expert consultation required (no baseball stats, schema, or API questions) -- this is a straightforward rewrite of four artifacts with clear scope and no domain ambiguity. PM + CA collaborative refinement confirmed the approach and identified AC improvements during epic formation. Confirmed by team lead: `codex exec --ephemeral` with a path-based prompt works correctly (2,362 tokens vs thousands with embedded content).

## Goals
- Reduce generated review prompts from thousands of lines to under 50 lines (spec review) or by the size of the embedded rubric (code review)
- Preserve the same review outcome: Codex reviews artifacts against the rubric
- Apply the fix to all four review artifacts (both skills + both scripts)

## Non-Goals
- Changes to the rubric files (`.project/codex-spec-review.md`, `.project/codex-review.md`)
- Changes to the `spec-review` or `review-epic` skills (the in-process workflows that invoke the scripts)
- Changes to any agent definitions or CLAUDE.md workflows

## Success Criteria
- All four artifacts generate prompts that contain file paths (not file contents) for rubrics and (where applicable) epic directories
- Both skills' agent roster tables are still inlined (small and useful as immediate context)
- Spec review prompts are under 50 lines each; code review prompts' rubric sections are under 5 lines (diffs remain embedded)
- Codex can still execute reviews successfully using lean prompts from all four paths

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-080-01 | Rewrite codex-prompt-spec to path-based prompt | DONE | None | claude-architect |
| E-080-02 | Rewrite codex-spec-review.sh to path-based prompt | DONE | None | software-engineer |
| E-080-03 | Rewrite codex-review.sh rubric embedding to path-based | DONE | None | software-engineer |
| E-080-04 | Rewrite codex-prompt-code rubric embedding to path-based | DONE | None | claude-architect |

## Dispatch Team
- claude-architect (E-080-01, E-080-04: skill files)
- software-engineer (E-080-02, E-080-03: shell scripts)

## Technical Notes

### Shared
- Spec review rubric: `.project/codex-spec-review.md`. Code review rubric: `.project/codex-review.md`.
- All paths in the generated prompts (epic directory, rubric) must be absolute so Codex can resolve them unambiguously.
- All four stories have no file conflicts and can execute in parallel.

### E-080-01 (Skill -- claude-architect)
- The skill file is at `.claude/skills/codex-prompt-spec/SKILL.md`
- This is a context-layer file (skill), so it routes to claude-architect per the dispatch routing table.
- The key change: Steps 1 and 2 currently use Glob+Read to gather file contents. They should be simplified to just resolve/verify paths. Step 4's prompt template should reference paths instead of embedding contents, and instruct Codex to read the files itself.
- The agent roster table in Step 3 remains unchanged -- it is small enough to inline and provides useful immediate context for Codex's team recommendation.
- Anti-patterns 3 and 4 should be reworded for the path-based approach (not removed). Anti-pattern 3 still guards against embedding content in the skill file itself. Anti-pattern 4 still scopes the prompt to the epic directory and rubric -- no extra paths for externally referenced documents.

### E-080-02 (Script -- software-engineer)
- The script is at `scripts/codex-spec-review.sh`
- The script's argument parsing, validation, and `codex exec --ephemeral -` invocation remain unchanged. Only the `assemble_prompt()` function changes.
- The script already resolves the epic directory to an absolute path (lines 114-120). Carry that resolved path into the prompt output.
- The `--note`/`--note-file` runtime context is user-provided at execution time and must remain inline in the prompt (it cannot be replaced with a path).
- The script has no dedicated tests. Correctness is verified by running it.

### E-080-03 (Script -- software-engineer)
- The script is at `scripts/codex-review.sh`
- The code review rubric is at `.project/codex-review.md` (distinct from the spec review rubric).
- Only `assemble_review_prompt()` changes. The rubric `cat` call becomes a path reference. The diff embedding (`echo "${diff_content}"`) remains unchanged -- diffs are runtime-generated and have no on-disk path.
- Argument parsing, mode handling (`uncommitted`/`base`/`commit`), diff generation functions, error handling, and all three `codex exec --ephemeral -` invocations are unchanged.
- The script has no dedicated tests. Correctness is verified by running it or inspecting captured output.

### E-080-04 (Skill -- claude-architect)
- The skill file is at `.claude/skills/codex-prompt-code/SKILL.md`
- This is a context-layer file (skill), so it routes to claude-architect per the dispatch routing table.
- The key change: Step 4 currently reads the rubric via Read and Step 6 embeds its full contents in the prompt template. Step 4 should become an existence check only. Step 6's rubric section should become a path reference with a read instruction for Codex.
- The diff (Step 2) is runtime-generated from git commands and MUST remain embedded in the generated prompt. This is the fundamental asymmetry with E-080-01.
- The agent roster table (Step 5) remains unchanged -- small, static, useful as immediate context.
- Anti-pattern 3 should be strengthened to cover both the skill file and the generated prompt (not removed).
- The size check (Step 3) already runs before the rubric step and counts only diff content. No changes needed.
- The epic's Non-Goals section must also be updated (removes incorrect exclusion of this skill).

## Open Questions
None.

## History
- 2026-03-08: Created. Single-story bug fix for token-wasteful prompt generation.
- 2026-03-08: Refined by PM + claude-architect. AC-3 clarified (absolute paths). AC-7/AC-8 tightened from "remove or rewrite" to "rewrite" with specific guidance. AC-9 added for Anti-pattern 4 rewording. Technical Notes expanded with path and anti-pattern guidance.
- 2026-03-08: Scope expanded per user direction. Added E-080-02 (codex-spec-review.sh script rewrite). Epic now covers both spec review artifacts. Dispatch Team expanded to include software-engineer. Technical Notes split into Shared/E-080-01/E-080-02 sections. Stories are parallel (no file conflicts).
- 2026-03-08: Codex spec review triage (4 P2 findings). F1 REFINE: added line-count ACs (E-080-01 AC-10 under 50 lines, E-080-02 AC-7 under 25 lines). F2 REFINE: replaced broad AC-5 with AC-5a (note flags) and AC-5b (error paths) in E-080-02. F3 REFINE: Background consultation text clarified. F4 REFINE (E-080-02 only): DoD strengthened with end-to-end run and no-embedded-content verification.
- 2026-03-08: Scope expanded again per user direction. Added E-080-03 (codex-review.sh rubric-only path conversion). Same optimization as E-080-02 but for the code review script -- rubric becomes a path reference, diff stays embedded. Epic title, overview, background, goals, non-goals, success criteria, dispatch team, and shared technical notes updated to reflect all three artifacts. `codex-review.sh` removed from Non-Goals.
- 2026-03-08: All three stories DONE. E-080-01 verified by main session (context-layer). E-080-02 and E-080-03 approved by code-reviewer. Epic COMPLETED.
- 2026-03-08: Reopened. Added E-080-04 (codex-prompt-code skill rubric path conversion). Original Non-Goals incorrectly excluded this skill ("Codex is not executing in-repo") -- E-080-01 proved otherwise. PM consulted CA and SE before writing the story. Non-Goals corrected.
- 2026-03-08: E-080-04 DONE, verified by main session (context-layer). All four stories complete. Epic COMPLETED. Documentation assessment: no documentation impact. Context-layer assessment: all six triggers no -- no new commands, agents, capabilities, workflows, conventions, or dependencies.
- 2026-03-08: Closure assessments. Documentation assessment: No documentation impact (internal tooling, no user-facing docs affected). Context-layer assessment: All six triggers evaluated — no triggers fired (no new commands, agents, capabilities, workflows, conventions, or dependencies).
- 2026-03-08: Epic unarchived and reopened as ACTIVE. Added E-080-04 (codex-prompt-code skill rubric path conversion). The original Non-Goals incorrectly excluded this skill ("Codex is not executing in-repo") -- E-080-01 proved otherwise. CA consulted on change scope (confirmed 6 sections need updating, diff stays embedded). SE consulted for lessons from E-080-02/03 (flagged copy-paste portability concern; resolved by E-080-01 precedent). Epic overview, background, goals, non-goals, success criteria, dispatch team, and technical notes updated.
