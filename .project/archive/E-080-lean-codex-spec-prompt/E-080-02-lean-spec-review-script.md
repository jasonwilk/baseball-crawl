# E-080-02: Rewrite codex-spec-review.sh to path-based prompt

## Epic
[E-080: Lean Codex Spec Review Prompt](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `codex-spec-review.sh` script will assemble a lean prompt containing file paths and review instructions instead of embedding full file contents. Codex reads the files itself via its repository access. The script's argument handling, validation, and `codex exec --ephemeral -` invocation pattern remain unchanged.

## Context
The script's `assemble_prompt()` function currently `cat`s the full rubric file and every `.md` file in the epic directory into the assembled prompt piped to `codex exec`. This produces the same token-waste problem as the skill (E-080-01). The team lead confirmed that Codex can read files by path -- a test run produced 2,362 tokens vs thousands with embedded content.

The script is the "in-process" review path (runs Codex directly), while the skill (E-080-01) is the "copy-paste" path (generates a prompt for manual use). Both need the same fix, but they are different files with different implementers.

## Acceptance Criteria
- [ ] **AC-1**: The `assemble_prompt()` function no longer `cat`s the rubric file. It outputs the rubric file path and instructs Codex to read it.
- [ ] **AC-2**: The `assemble_prompt()` function no longer `cat`s individual `.md` files from the epic directory. It outputs the epic directory path and instructs Codex to read all `.md` files in that directory.
- [ ] **AC-3**: The assembled prompt includes: (a) the absolute rubric file path, (b) the absolute epic directory path, (c) instructions for Codex to read those files and review against the rubric, (d) cite story IDs and AC labels for findings.
- [ ] **AC-4**: The `--note` and `--note-file` runtime context is still included in the assembled prompt (this content is user-provided at runtime and cannot be replaced with a path).
- [ ] **AC-5a**: `--note` and `--note-file` still append a labeled runtime context section to the assembled prompt.
- [ ] **AC-5b**: Error paths remain unchanged: missing epic-dir argument prints usage and exits non-zero; non-existent epic directory, missing `epic.md`, and missing rubric file each print a descriptive error to stderr and exit non-zero.
- [ ] **AC-6**: The script header comment is updated to reflect the path-based approach (no references to "file contents" being assembled).
- [ ] **AC-7**: The assembled prompt (excluding any `--note`/`--note-file` content) is under 25 lines.

## Technical Approach
The `assemble_prompt()` function in `scripts/codex-spec-review.sh` needs rewriting. The validation section (lines 107-139) stays the same -- it already resolves the epic directory to an absolute path and validates both the directory and rubric file exist. The `assemble_prompt()` function (lines 145-184) changes: instead of `cat`ing files, it outputs paths and instructions. The `find` loop that iterates `.md` files is replaced with a single line giving the directory path. The rubric `cat` is replaced with a path reference. The REVIEW REQUEST section gains instructions telling Codex to read the files.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `scripts/codex-spec-review.sh` (modify)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)
- [ ] Script runs end-to-end against a real epic directory without error (manual verification)
- [ ] Assembled prompt contains no file contents -- only paths, instructions, and optional runtime note

## Notes
- The `codex-review.sh` (code review) script is NOT in scope -- it assembles diffs which must be embedded.
- The script has no dedicated test file. The story does not require adding tests -- the script is a thin wrapper around `codex exec` and its correctness is verified by running it.
- If `codex` is not available in the environment, the implementer can verify by capturing `assemble_prompt()` output (e.g., commenting out the final pipe and redirecting to a file) and inspecting the prompt shape.
