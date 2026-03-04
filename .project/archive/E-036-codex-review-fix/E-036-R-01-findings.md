# E-036-R-01: Research Findings -- How to Pass Custom Rubric to codex review

**Date**: 2026-03-03
**Question**: How do we deliver our project rubric to `codex review` when using `--uncommitted`, `--base`, or `--commit` flags?

---

## CLI Help Output

### `codex review --help` (from user-verified output, v0.107.0)

```
Usage: codex review [OPTIONS] [PROMPT]

Options:
  --uncommitted   Review staged, unstaged, and untracked changes
  --base <BRANCH> Review changes against a base branch
  --commit <SHA>  Review a specific commit
```

**Key finding**: `[PROMPT]` is the only mechanism for custom instructions, and it is mutually exclusive with `--uncommitted`, `--base`, and `--commit`. The CLI explicitly rejects combinations:
- `codex review --uncommitted - <rubric` -> error: `--uncommitted` cannot be used with `[PROMPT]`
- `codex review --base <branch> - <rubric` -> error: `--base` cannot be used with `[PROMPT]`
- `codex review --commit <sha> - <rubric` -> error: `--commit` cannot be used with `[PROMPT]`

### No Additional Flags for Custom Instructions

The `codex review` subcommand has no flags for:
- `--instructions` or `--system-prompt`
- `--config` or `--rules`
- Any mechanism to specify custom review criteria alongside a diff-scoped flag

## Research Question Answers

### Q1: Does `codex review` accept any flag for custom instructions?
**No.** The only input mechanism is `[PROMPT]`, which is mutually exclusive with all three diff-scope flags. No `--instructions`, `--config`, or `--system-prompt` flag exists.

### Q2: Does the `codex` CLI have a global config mechanism?
**No project-level config mechanism found.** No `--config` or `--instructions` global flag exists in the `codex` CLI. The Codex CLI reads `CODEX_HOME` for global settings (model selection, API keys) but does not support per-project review instructions.

### Q3: Does Codex read project-level config files?
**No.** Exhaustive filesystem search confirms no Codex config files exist in the repository:
- No `codex.json`, `codex.toml`, `.codexrc`, `.codex/` anywhere in the repo
- No convention for project-level Codex review configuration found in the CLI

### Q4: Does Codex respect any environment variable for custom review instructions?
**No.** Codex environment variables (`OPENAI_API_KEY`, `CODEX_HOME`, etc.) control authentication and runtime behavior, not review content. No `CODEX_INSTRUCTIONS` or equivalent env var exists.

### Q5: Can `codex exec` be used as a fallback with assembled diff + rubric?
**Yes -- this is the recommended approach.** The `codex exec --ephemeral -` pattern is already proven in the spec-review wrapper (`scripts/codex-spec-review.sh`). It accepts arbitrary prompt content via stdin, including assembled rubric + diff content. The pattern is:

```bash
# Prototype for "uncommitted" mode:
{
    cat "${RUBRIC_FILE}"
    echo ""
    echo "=== CHANGES TO REVIEW ==="
    echo ""
    git diff HEAD
    git diff --cached
    git diff --name-only --diff-filter=A HEAD  # untracked awareness
} | codex exec --ephemeral -
```

For each mode, the script assembles the rubric + the appropriate diff:
- **uncommitted**: `git diff` (unstaged) + `git diff --cached` (staged) + untracked files
- **base**: `git diff <branch>...HEAD`
- **commit**: `git show <sha>`

This approach:
- Delivers the full rubric content to Codex
- Includes the exact diff content that `codex review` would have seen
- Uses a proven, working CLI pattern (`codex exec --ephemeral -`)
- Preserves the same user-facing interface (same modes, same syntax)

### Q6: Are there other codex subcommands that could serve this purpose?
**No.** The relevant subcommands are `codex review` (diff-scoped, no custom instructions) and `codex exec` (arbitrary prompt, our fallback). No other subcommand bridges the gap.

## Recommendation for E-036-01

**Use `codex exec --ephemeral -` with assembled rubric + diff for all three modes.**

### Implementation Guidance

1. **Replace all three `codex review` invocations** with `codex exec --ephemeral -` invocations that pipe assembled prompts.

2. **Assemble the prompt for each mode** using a shell function:

```bash
assemble_review_prompt() {
    local diff_content="$1"

    cat "${RUBRIC_FILE}"
    echo ""
    echo "======================================================================"
    echo "CHANGES TO REVIEW"
    echo "======================================================================"
    echo "${diff_content}"
    echo ""
    echo "======================================================================"
    echo "REVIEW REQUEST"
    echo "======================================================================"
    echo "Please review the changes above against the code-review rubric."
    echo "Follow the rubric's Review Priorities in order."
    echo "Cite file and line number for every finding."
    echo "If the review is clean, state explicitly: \"No findings.\""
}
```

3. **Generate diffs per mode**:
   - `uncommitted`: Combine `git diff` + `git diff --cached` + list untracked files. For untracked files, consider using `git diff --no-index /dev/null <file>` or simply `cat` with a header.
   - `base <branch>`: `git diff "${BRANCH}"...HEAD`
   - `commit <sha>`: `git show "${SHA}"`

4. **Handle empty diffs gracefully**: If the diff is empty, print a message ("No changes to review") and exit 0 rather than sending an empty prompt to Codex.

5. **Preserve the existing user-facing interface**: Same modes (`uncommitted`, `base`, `commit`), same syntax, same `usage()` output.

6. **Update the header comment** to document that the script uses `codex exec` (not `codex review`) because `codex review` does not support custom instructions alongside diff-scope flags.

### Why This Approach

- **Proven pattern**: `codex exec --ephemeral -` already works in `scripts/codex-spec-review.sh`
- **Full rubric delivery**: The entire rubric is included in the prompt
- **Equivalent diff content**: The script generates the same diffs that `codex review` would have used internally
- **No interface change**: Users call the script the same way; the internal mechanism changes
- **No external dependencies**: No config files, env vars, or Codex version-specific features needed

### What This Approach Cannot Do

- `codex review` may have internal diff-analysis features (e.g., understanding file history, blame context) that raw diff + `codex exec` does not replicate. For our use case (rubric-guided review of changes), raw diffs are sufficient.
- `codex review` may format output differently than `codex exec`. The review quality should be equivalent since the same model sees the same content, but the output formatting may differ.

---

## Evidence Basis

- CLI behavior confirmed by user testing against codex v0.107.0
- Filesystem search for config files performed via glob/grep (no matches)
- `codex exec --ephemeral -` pattern verified working in `scripts/codex-spec-review.sh` (line 189)
- Prompt assembly pattern modeled after `scripts/codex-spec-review.sh` `assemble_prompt()` function (lines 145-184)
