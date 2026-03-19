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

1. **The rubric file exists.** Verify `/workspaces/baseball-crawl/.project/codex-review.md` is present. If missing, report the error and stop. For the prompt-generation path, also read the file contents (needed for embedding in Step 3).

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

## Epic Worktree Path

When this skill is invoked during the "and review" chain (implement skill Phase 4), the epic worktree path is available from the dispatch context. The implement skill creates the epic worktree in Phase 2 Step 1 at `/tmp/.worktrees/baseball-crawl-E-NNN/` and carries it through the entire dispatch lifecycle. Phase 4 invokes this skill after all stories are DONE but before closure -- the epic worktree contains all accumulated story patches (the complete epic diff against main).

When this skill is invoked standalone (not during dispatch), no epic worktree path is available. The skill operates on the main checkout as before.

---

## Headless Path

### Step 1: Run the script

Run the code review script via Bash in the foreground. When an epic worktree path is available (during the "and review" chain), pass `--workdir <epic-worktree-path>` so that `uncommitted` mode generates the diff from the epic worktree against main:

**During "and review" chain (epic worktree available):**
```
timeout 600 ./scripts/codex-review.sh --workdir <epic-worktree-path> <mode> [args]
```

**Standalone invocation (no epic worktree):**
```
timeout 600 ./scripts/codex-review.sh <mode> [args]
```

Examples:
- `timeout 600 ./scripts/codex-review.sh --workdir /tmp/.worktrees/baseball-crawl-E-137 uncommitted`
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

**Triage is advisory.** The team assesses findings and recommends action (fix, defer, dismiss) but does NOT implement changes directly. Confirmed findings proceed to Step 5 (Remediation Loop).

### Step 5: Remediation loop

After triage completes (whether via triage team or main session assessment), any findings confirmed for remediation enter the remediation loop. If all findings were dismissed or marked false positive during triage, skip to Step 7. Remediation is authorized by the post-review remediation exception in `workflow-discipline.md`'s Work Authorization Gate -- the codex-review skill does not declare its own authorization model.

**Spawning mechanics** depend on context:

- **(a) "And review" chain** (invoked from implement skill Phase 4): The dispatch team is still active. A fresh implementer is spawned into the **epic worktree** (without `isolation: "worktree"`) using the agent routing table to select the appropriate agent type for each finding's domain. The original dispatch team implementers may have been shut down, so a fresh spawn is the reliable path. PM is already on the team for disposition tracking. See the implement skill Phase 4a for the full remediation spawn context.
- **(b) Standalone post-dev review** (invoked directly by the user): No dispatch team exists. The main session creates a remediation team using the agent routing table (`/.claude/rules/agent-routing.md`) to select the appropriate implementer type(s) for the findings' domains (not hard-coded to SE), plus PM for disposition tracking.

For each finding confirmed for remediation, route it to the implementer with the finding details. The implementer:

1. **Validates** the finding -- confirming it is a real issue or identifying it as a false positive.
2. **Remediates** confirmed issues. Where the implementer works depends on context:
   - **(a) "And review" chain**: The epic worktree is still active (closure has not happened yet). The implementer applies fixes in the **epic worktree**. Fixes are NOT committed -- they accumulate in the epic worktree and are included in the closure merge sequence (Phase 5).
   - **(b) Standalone post-dev review**: No epic worktree exists. The implementer works in the main checkout.
3. Reports completion with a change summary (files changed and nature of fix).

**Remediation fixes are NOT re-reviewed.** PM records dispositions. If the user wants another review pass after remediation, they invoke a separate codex-review.

### Step 6: PM disposition tracking

PM records all findings with their dispositions. Each finding gets one of three dispositions:

- **FIXED**: With a change summary describing what was fixed (files, nature of change) -- not a git commit SHA, since commits happen after team shutdown.
- **DISMISSED**: With a reason explaining why the finding was not actionable.
- **FALSE POSITIVE**: With an explanation of why the finding does not apply.

**Recording location** depends on context:

- **(a) "And review" chain**: PM records in the dispatch epic's History section.
- **(b) Standalone post-dev review**: PM records in a remediation log at `/.project/research/codex-review-YYYY-MM-DD-remediation.md` (standalone reviews may not map to a single epic).

### Step 7: Wrap up

- If this was an "and review" chain, control returns to the implement skill's Phase 4, which proceeds to Phase 4b (CR integration review).
- If this was a standalone review, present the disposition summary to the user and offer to commit changes.

---

## Prompt-Generation Path

### Step 1: Gather the diff

Use Bash to gather the diff content based on the mode. When an epic worktree path is available (during the "and review" chain), use `git -C <epic-worktree-path>` to run git commands from the epic worktree.

**Mode: `uncommitted`**

**During "and review" chain (epic worktree available):**

Run a single command to get all changes relative to main:
```
git -C <epic-worktree-path> diff main
```

This produces the complete epic diff (all accumulated story patches against main).

**Standalone invocation (no epic worktree):**

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

When an epic worktree path is available, use it; otherwise omit `-C` (runs from the main checkout):
```
git -C <epic-worktree-path> diff <branch>...HEAD   # during "and review" chain
git diff <branch>...HEAD                            # standalone
```

**Mode: `commit <sha>`**

Same resolution — use the epic worktree path if available, otherwise the main checkout:
```
git -C <epic-worktree-path> show <sha>              # during "and review" chain
git show <sha>                                      # standalone
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

Build the prompt matching the format used by `scripts/codex-review.sh`. The rubric content is **embedded directly** in the prompt (not referenced by path) so that codex in ephemeral mode can access it without repository file access:

```
CODE-REVIEW REQUEST

REVIEW RUBRIC
{rubric file contents — read from /workspaces/baseball-crawl/.project/codex-review.md}

CHANGES TO REVIEW (mode: {mode label})
{diff content}

Instructions:
1. Review the changes above against the rubric. Follow its Review Priorities in order.
2. Cite file and line number for every finding.
3. Group findings by priority level.
4. If the review is clean, state explicitly: "No findings."
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
  |       Run codex-review.sh [--workdir <epic-worktree-path>] <mode> [args]
  |       Capture and present findings
  |       No changes? -> Report and stop
  |       No findings? -> Report clean review, stop
  |       Findings? -> Offer advisory triage (agents from CLAUDE.md)
  |       User accepts? -> Spawn triage team
  |       User declines? -> Stop (no remediation)
  |       Triage complete, findings confirmed for remediation?
  |         NO -> Stop
  |         YES -> Remediation loop:
  |           Spawn fresh implementer (epic worktree for "and review" chain, main checkout for standalone)
  |           Implementer validates each finding (real issue or false positive)
  |           Implementer remediates in epic worktree ("and review") or main checkout (standalone)
  |           PM records dispositions (FIXED/DISMISSED/FALSE POSITIVE)
  |             "And review" chain -> epic History section
  |             Standalone review -> .project/research/codex-review-YYYY-MM-DD-remediation.md
  |           Fixes are NOT re-reviewed
  |           Present disposition summary, offer to commit
  |
  +---> PROMPT-GEN PATH:
          Gather diff via Bash + Read
          Empty diff? -> Report "no changes", stop
          Size check (5k warn, 10k refuse)
          Assemble lean prompt (request header, embedded rubric, diff, instructions)
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
3. **Do not embed rubric content in this skill file.** The rubric is read at runtime and embedded in the generated prompt (both script and prompt-generation paths). The rubric's content is NOT hardcoded in this skill file -- it is always read fresh from `.project/codex-review.md`.
4. **Do not summarize the diff in prompt-generation.** The prompt must contain the complete diff content. Codex needs the full code to perform a meaningful review.
5. **Do not add separator walls, "Begin your response with" instructions, or team recommendation blocks to prompts.** The lean format has no ceremony.
6. **Do not implement fixes during triage.** Triage is advisory -- the triage team assesses and recommends but does NOT write code. Implementation happens in the separate remediation phase (Step 5), which is authorized by the post-review remediation exception in `workflow-discipline.md`'s Work Authorization Gate.
