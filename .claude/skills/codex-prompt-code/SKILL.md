# Skill: codex-prompt-code

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "codex review prompt"
- "generate codex review prompt"
- "code review prompt"
- "build me a codex review prompt"
- Any request to generate a copy-paste code review prompt for Codex

The discriminator is the word "code" (or the absence of "spec"). If the user says "spec review prompt" or similar, that is the spec review prompt skill, not this one.

---

## Purpose

Generate a code review prompt that the user can copy-paste into Codex. The prompt includes the diff (with full untracked file contents), a path reference to the project's code review rubric, and a static agent roster so Codex can recommend a review team. Codex reads the rubric file itself using its repository access.

This skill does NOT execute the review. It assembles the prompt and presents it to the user in a fenced code block.

---

## Prerequisites

Before executing this workflow, verify:

1. **You are in the baseball-crawl repository.** The rubric file and agent ecosystem must be accessible.
2. **The rubric file exists.** Confirm `/workspaces/baseball-crawl/.project/codex-review.md` is present.

---

## Step 1: Determine Diff Mode

Parse the user's request to determine the diff mode. The three modes match those supported by `scripts/codex-review.sh`:

| Mode | Trigger | Example |
|------|---------|---------|
| `uncommitted` (default) | No mode specified, or "uncommitted" | "codex review prompt", "generate codex review prompt for uncommitted" |
| `base <branch>` | User specifies a base branch | "codex review prompt base main", "code review prompt against develop" |
| `commit <sha>` | User specifies a commit SHA | "codex review prompt commit abc1234" |

If the user does not specify a mode, default to `uncommitted`.

---

## Step 2: Gather the Diff

Use Bash to gather the diff content based on the mode determined in Step 1.

### Mode: `uncommitted`

Run three commands via Bash:

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

For each untracked file returned in (c):
- Skip binary files. To detect binary files, check if `file --brief --mime-type <path>` returns a MIME type that does NOT start with `text/`. If a file is binary, note it in the diff output as `--- FILE: <path> --- [SKIPPED: binary file]` and move on.
- For text files, use Read to get the full contents of each file.

Assemble the diff output in this structure:

```
--- Staged changes ---
<staged diff output>

--- Unstaged changes ---
<unstaged diff output>

--- Untracked files ---
--- FILE: path/to/file1.py ---
<full contents of file1.py>

--- FILE: path/to/file2.md ---
<full contents of file2.md>
```

Omit any section that is empty (e.g., if there are no staged changes, omit the "Staged changes" section entirely).

### Mode: `base <branch>`

Run via Bash:
```
git diff <branch>...HEAD
```

### Mode: `commit <sha>`

Run via Bash:
```
git show <sha>
```

### Empty diff

If all diff commands return empty output (no staged changes, no unstaged changes, no untracked files for `uncommitted` mode; empty diff for `base` or `commit` mode), report to the user: "No changes found for the specified mode. Nothing to generate a review prompt for." Stop the workflow.

---

## Step 3: Size Check

Count the total number of lines in the assembled diff content (including full untracked file contents from Step 2). Apply these thresholds BEFORE proceeding to prompt assembly:

| Total Lines | Action |
|-------------|--------|
| Under 5,000 | Proceed normally |
| 5,000 to 10,000 (inclusive) | Warn the user: "The diff is approximately N lines. This is large for a single Codex review -- results may be less focused. Proceeding with assembly." Then proceed |
| Over 10,000 | Refuse to assemble. Tell the user: "The diff is approximately N lines, which exceeds the 10,000-line limit for a single review prompt. Suggestions: narrow the scope to specific directories or files, review a single commit instead of the full diff, or split changes across multiple review prompts." Stop the workflow |

---

## Step 4: Verify the Rubric Path

Confirm that `/workspaces/baseball-crawl/.project/codex-review.md` exists (e.g., via Glob or Bash `test -f`). Do NOT Read its contents -- the generated prompt will instruct Codex to read the rubric itself.

If the file does not exist, report the error to the user and stop.

---

## Step 5: Verify Agent Roster

Before assembling, check the agent roster table below against the CLAUDE.md Agent Ecosystem section (which is already in your ambient context). If agents have been added, removed, or renamed since this skill was written, update the table in the generated prompt to match the current ecosystem.

**Static Agent Roster (current as of skill creation):**

| Agent | Role |
|-------|------|
| claude-architect | Designs and manages agents, CLAUDE.md, rules, skills |
| product-manager | Product Manager -- owns what to build, why, and in what order |
| baseball-coach | Domain expert -- translates coaching needs into technical requirements |
| api-scout | Explores GameChanger API, maintains API spec, manages credential patterns |
| data-engineer | Database schema design, ETL pipelines, SQLite architecture |
| software-engineer | Python implementation, testing, general coding work |
| docs-writer | Documentation specialist for admin/developer and coaching staff audiences |
| ux-designer | UX/interface designer for coaching dashboard and UI work |
| code-reviewer | Adversarial code reviewer -- verifies ACs and code quality before stories are marked DONE |

---

## Step 6: Assemble and Present the Prompt

Assemble the complete prompt using the template below. Present it to the user inside a single fenced code block (triple backticks) so they can copy-paste it directly into Codex.

**Prompt Template:**

```
======================================================================
CODE-REVIEW RUBRIC
======================================================================
Read the rubric at: /workspaces/baseball-crawl/.project/codex-review.md

Apply the rubric's Review Priorities in order when reviewing the
changes below.

======================================================================
CHANGES TO REVIEW (mode: <mode label>)
======================================================================
<full diff content from Step 2>

======================================================================
AGENT ROSTER
======================================================================
The following agents are available in this project for follow-up work:

| Agent | Role |
|-------|------|
| claude-architect | Designs and manages agents, CLAUDE.md, rules, skills |
| product-manager | Product Manager -- owns what to build, why, and in what order |
| baseball-coach | Domain expert -- translates coaching needs into technical requirements |
| api-scout | Explores GameChanger API, maintains API spec, manages credential patterns |
| data-engineer | Database schema design, ETL pipelines, SQLite architecture |
| software-engineer | Python implementation, testing, general coding work |
| docs-writer | Documentation specialist for admin/developer and coaching staff audiences |
| ux-designer | UX/interface designer for coaching dashboard and UI work |
| code-reviewer | Adversarial code reviewer -- verifies ACs and code quality before stories are marked DONE |

======================================================================
REVIEW REQUEST
======================================================================
Please review the changes above against the code-review rubric.

Begin your response with: "This is peer feedback from Codex"

Follow the rubric's Review Priorities in order. Cite file and line number
for every finding. Group findings by priority level.

If the review is clean, state explicitly: "No findings."

After your review, recommend starting a team of agents to address the
findings. The team should include the product-manager and the relevant
domain experts from the Agent Roster above. The subject matter experts
and PM should decide together which feedback to refine into the epic,
which code to fix, and which to defer.
```

Replace `<full diff content from Step 2>` and `<mode label>` with the actual content gathered in previous steps. The mode label should be one of: `uncommitted`, `base <branch>`, or `commit <sha>`.

If the size warning from Step 3 applies (5,000-10,000 lines), include the warning text BEFORE the fenced code block, not inside it.

---

## Workflow Summary

```
User says "codex review prompt" (or variant)
  |
  v
Load this skill
  |
  v
Step 1: Determine diff mode (default: uncommitted)
  |
  v
Step 2: Gather diff via Bash + Read (full untracked file contents)
  |
  +---> Empty diff? -> Report "no changes" and stop
  |
  v
Step 3: Size check
  |
  +---> Over 10,000 lines? -> Refuse, suggest mitigations, stop
  +---> 5,000-10,000 lines? -> Warn user, continue
  |
  v
Step 4: Verify rubric exists at .project/codex-review.md
  |
  v
Step 5: Verify agent roster against CLAUDE.md
  |
  v
Step 6: Assemble prompt, present in fenced code block
```

---

## Edge Cases

### Empty diff
If all diff commands return empty results, report "No changes found" and stop. Do not assemble an empty prompt.

### Very large diff (size thresholds)
See Step 3. The 5,000-line boundary is exact -- 4,999 lines proceeds silently, 5,000 lines triggers the warning. The 10,000-line boundary is also exact -- 10,000 lines warns and proceeds, 10,001 lines refuses.

### Untracked binary files
Detected via `file --brief --mime-type`. Binary files are skipped with a note in the diff output: `--- FILE: <path> --- [SKIPPED: binary file]`. They do not count toward the size threshold.

### Rubric file missing
If `/workspaces/baseball-crawl/.project/codex-review.md` does not exist, report the error and stop. Do not attempt to generate a prompt without the rubric.

### No untracked files
If `git ls-files --others --exclude-standard` returns nothing, simply omit the "Untracked files" section. This is normal and not an error.

---

## Anti-Patterns

1. **Do not execute the prompt.** This skill generates a prompt for copy-paste into Codex. It does NOT run codex, invoke any review tool, or apply any review findings. The user takes the output and pastes it elsewhere.
2. **Do not modify the rubric file.** The rubric at `.project/codex-review.md` is a shared project artifact. This skill reads it; it never writes to it.
3. **Do not embed rubric content in this skill file or in the generated prompt.** The rubric is referenced by absolute path; Codex reads it directly.
4. **Do not summarize the diff.** The prompt must contain the complete diff content. Codex needs the full code to perform a meaningful review.
5. **Do not dynamically read agent definition files.** The roster table is static and verified against CLAUDE.md (ambient context). Reading 9 agent files at execution time wastes context for information that rarely changes.
