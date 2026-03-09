# Skill: codex-review

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "review with codex", "codex review", "codex review E-NNN"
- "code review", "code review E-NNN"
- "review epic", "review epic E-NNN"
- "post-dev review", "post-dev review E-NNN"
- "codex review prompt", "code review prompt"
- "generate codex review prompt", "generate code review prompt"
- Any request that implies running a codex code review on implementation changes

The absence of **"spec"** is the mode discriminator. If the user says "spec review" or "codex spec review", that is the `codex-spec-review` skill, not this one.

---

## Execution Path Detection

This skill supports two execution paths, detected from the user's trigger phrase:

- **Headless (default)**: The user's phrase does NOT contain "prompt". Claude runs the review via the script, captures output, presents findings, and offers advisory triage.
- **Prompt generation**: The user's phrase CONTAINS "prompt" (e.g., "codex review prompt", "code review prompt"). Claude gathers the diff, assembles a lean prompt, and presents it in a fenced code block for copy-paste. No execution, no triage.

---

## Prerequisites

Before executing either path, verify:

1. **The rubric file exists.** Verify `/workspaces/baseball-crawl/.project/codex-review.md` is present. Do NOT read its contents. If missing, report the error and stop.

---

## Diff Mode Detection

Parse the user's request to determine the diff mode:

| Mode | Trigger | Example |
|------|---------|---------|
| `uncommitted` (default) | No mode specified, or "uncommitted" | "codex review", "code review prompt" |
| `base <branch>` | User specifies a base branch | "codex review base main", "code review prompt against develop" |
| `commit <sha>` | User specifies a commit SHA | "codex review commit abc1234" |

If the user does not specify a mode, default to `uncommitted`.

---

## Headless Path

### Step 1: Run the script

Run the code review script via Bash in the foreground:

```
timeout 600 ./scripts/codex-review.sh <mode> [args]
```

Examples:
- `timeout 600 ./scripts/codex-review.sh uncommitted`
- `timeout 600 ./scripts/codex-review.sh base main`
- `timeout 600 ./scripts/codex-review.sh commit abc1234`

### Step 2: Handle errors

- **Exit code 124 (timeout)**: Codex timed out after 10 minutes. Report the timeout to the user and ask how to proceed. Do not retry automatically.
- **Other non-zero exit codes**: The script itself failed (codex not installed, missing rubric). Report the specific error message to the user and stop.

### Step 3: Evaluate output

- If the script reports **"No uncommitted changes to review"** or **"No diff against..."**: Report this to the user and stop. There is nothing to review.
- If the script reports **"No findings."**: Report "Codex review completed with no findings -- clean review" to the user. Skip triage. Workflow ends.
- If the script reports findings: present the full Codex findings to the user. Proceed to Step 4.

### Step 4: Offer advisory triage

After presenting findings, offer the user an advisory triage session:

1. Read the Codex findings and identify which domains they touch (schema, implementation, API, coaching, documentation, agent infrastructure, UX).
2. Map those domains to agents from CLAUDE.md's Agent Ecosystem table (ambient context at runtime -- do NOT use a hardcoded roster).
3. Offer to spawn a triage team with the relevant agents. The team composition depends on the findings' domains -- there is no fixed team.
4. If the user accepts, create the team and spawn agents. If the user declines, the workflow ends.

**Triage is advisory.** The team assesses findings and recommends action (fix, defer, dismiss) but does NOT implement changes directly. Implementation requires a story reference per the Work Authorization Gate (workflow-discipline.md).

---

## Prompt-Generation Path

### Step 1: Gather the diff

Use Bash to gather the diff content based on the mode.

**Mode: `uncommitted`**

Run three commands:

**(a) Staged changes:**
```
git diff --cached
```

**(b) Unstaged changes:**
```
git diff
```

**(c) Untracked files -- list names:**
```
git ls-files --others --exclude-standard
```

For each untracked file in (c):
- Skip binary files (check with `file --brief --mime-type <path>`; skip if it does NOT start with `text/`). Note skipped files as `--- FILE: <path> --- [SKIPPED: binary file]`.
- For text files, use Read to get the full contents.

Assemble the diff output:

```
--- Staged changes ---
<staged diff output>

--- Unstaged changes ---
<unstaged diff output>

--- Untracked files ---
--- FILE: path/to/file1.py ---
<full contents>

--- FILE: path/to/file2.md ---
<full contents>
```

Omit any section that is empty.

**Mode: `base <branch>`**

```
git diff <branch>...HEAD
```

**Mode: `commit <sha>`**

```
git show <sha>
```

**Empty diff**: If all diff commands return empty output, report "No changes found for the specified mode. Nothing to generate a review prompt for." Stop.

### Step 2: Size check

Count the total lines in the assembled diff content:

| Total Lines | Action |
|-------------|--------|
| Under 5,000 | Proceed silently |
| 5,000 to 10,000 | Warn: "The diff is approximately N lines. This is large for a single Codex review -- results may be less focused. Proceeding with assembly." Then proceed |
| Over 10,000 | Refuse: "The diff is approximately N lines, which exceeds the 10,000-line limit for a single review prompt. Suggestions: narrow the scope to specific directories or files, review a single commit instead of the full diff, or split changes across multiple review prompts." Stop |

### Step 3: Assemble the lean prompt

Build the prompt matching the format used by `scripts/codex-review.sh`:

```
CODE-REVIEW REQUEST

Rubric: /workspaces/baseball-crawl/.project/codex-review.md

CHANGES TO REVIEW (mode: {mode label})
{diff content}

Instructions:
1. Read the rubric at the path above.
2. Review the changes above against the rubric. Follow its Review Priorities in order.
3. Cite file and line number for every finding.
4. Group findings by priority level.
5. If the review is clean, state explicitly: "No findings."
```

The mode label is one of: `uncommitted`, `base <branch>`, or `commit <sha>`.

### Step 4: Present to the user

Present the assembled prompt inside a fenced code block (triple backticks) so the user can copy-paste it directly into Codex.

Do NOT execute the prompt. Do NOT offer triage. Prompt-generation path ends here.

---

## Workflow Summary

```
User says "codex review" or "code review prompt" (or variant)
  |
  v
Load this skill
  |
  v
Detect execution path: "prompt" in phrase? -> prompt-gen, else headless
  |
  v
Verify rubric exists at .project/codex-review.md
  |
  v
Determine diff mode (default: uncommitted)
  |
  +---> HEADLESS PATH:
  |       Run codex-review.sh <mode> [args]
  |       Capture and present findings
  |       No changes? -> Report and stop
  |       No findings? -> Report clean review, stop
  |       Findings? -> Offer advisory triage (agents from CLAUDE.md)
  |       User accepts? -> Spawn triage team
  |       User declines? -> Stop
  |
  +---> PROMPT-GEN PATH:
          Gather diff via Bash + Read
          Empty diff? -> Report "no changes", stop
          Size check (5k warn, 10k refuse)
          Assemble lean prompt (request header, rubric path, diff, instructions)
          Present in fenced code block
          Stop (no execution, no triage)
```

---

## Edge Cases

### Empty diff
If all diff commands return empty results, report "No changes found" and stop. Do not assemble an empty prompt or run the script with nothing to review.

### Rubric file missing
Report the error and stop. Do not attempt to generate a prompt or run the script without the rubric.

### Codex not installed (headless only)
The script checks for `codex` in PATH and exits with an error including install instructions. Report this error to the user and stop.

### Codex returns no findings (headless only)
Report "Clean review -- no findings" to the user. Do not offer triage. There is nothing to triage.

### No uncommitted changes (headless only)
The script exits cleanly with a message. Report this to the user. Suggest using `base main` mode if the changes were already committed.

### Very large diff (prompt-gen only)
See Step 2 size check. The headless path delegates size handling to the script.

### Untracked binary files (prompt-gen only)
Detected via `file --brief --mime-type`. Binary files are skipped with a note. They do not count toward the size threshold.

---

## Anti-Patterns

1. **Do not hardcode an agent roster in this skill file.** Agent selection for triage uses CLAUDE.md's Agent Ecosystem table at runtime (ambient context). This keeps the roster current without manual sync.
2. **Do not offer triage in the prompt-generation path.** Triage is headless-only. The prompt-gen path assembles and presents -- nothing more.
3. **Do not embed rubric content in this skill file or in generated prompts.** The rubric is referenced by absolute path; Codex reads it directly.
4. **Do not summarize the diff in prompt-generation.** The prompt must contain the complete diff content. Codex needs the full code to perform a meaningful review.
5. **Do not add separator walls, "Begin your response with" instructions, or team recommendation blocks to prompts.** The lean format has no ceremony.
6. **Do not implement fixes during triage.** Triage is advisory. Implementation requires a story reference per the Work Authorization Gate.
