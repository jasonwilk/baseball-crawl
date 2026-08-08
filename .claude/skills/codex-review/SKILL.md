---
name: codex-review
description: This skill should be used when the user says "codex review", "review with codex", "codex review E-NNN", "code review", "code review E-NNN", "review epic", "review epic E-NNN", "post-dev review", "codex review prompt", "code review prompt", "generate codex review prompt", or "generate code review prompt" -- or otherwise implies running a Codex code review on implementation changes. The ABSENCE of the word "spec" is the mode discriminator: a review request CONTAINING it belongs to the codex-spec-review skill, not this one. A trigger containing "prompt" selects the prompt-generation path; otherwise the headless path runs.
disable-model-invocation: true
---

# Skill: codex-review

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

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

## Headless Path

### Step 1: Run the script

Run the code review script via Bash in the foreground:

```
timeout 1200 ./scripts/codex-review.sh <mode> [args]
```

Examples:
- `timeout 1200 ./scripts/codex-review.sh uncommitted`
- `timeout 1200 ./scripts/codex-review.sh base main`
- `timeout 1200 ./scripts/codex-review.sh commit abc1234`

### Step 2: Handle errors

- **Exit code 124 (timeout)**: Codex timed out after 20 minutes. Report the timeout to the user and ask how to proceed. Do not retry automatically.
- **Other non-zero exit codes**: The script itself failed (codex not installed, missing rubric). Report the specific error message to the user and stop.

### Step 3: Evaluate output

- If the script reports **"No uncommitted changes to review"** or **"No diff against..."**: Report this to the user and stop. There is nothing to review.
- If the script reports **"No findings."**: Report "Codex review completed with no findings -- clean review" to the user. Skip triage. Workflow ends.
- If the script reports findings: do NOT present or characterize them yet -- the inline Bash result is only a truncated *preview*. Proceed to Step 4, whose read-receipt gate requires reading the full `RESULT_FILE` to completion BEFORE any finding is presented or triaged.

**Test-sweep caveat**: any test run Codex performs while reviewing is **best-effort** and advisory -- Codex reviews the diff, it is not the test gate. The authoritative check is lifecycle step 4 VERIFY (`python -m pytest tests/`, unpiped, against the main checkout). Do not treat a Codex "tests pass" statement as a substitute for it, and do not skip it because Codex ran tests.

### Step 4: Offer advisory triage

**Read-receipt gate — REQUIRED. Triage MUST NOT proceed until this is satisfied.**

The headless script streams Codex's output to the Bash tool result, which is truncated to a *preview* when the result is large. Triaging off that preview is the motivating failure mode: in the E-230 dispatch a triage question was fired off a ~2KB preview of a ~373KB persisted Codex result, mischaracterizing four valid findings as "2 LOW already-adjudicated." Before ANY triage tool or action runs against the review result you MUST:

1. **Locate the script-produced result file.** The script tees the full Codex output to a deterministic file and prints a receipt on stdout: a `RESULT_FILE=<path>` line, that file's `wc -l`, and its `tail -n1`. Read that `RESULT_FILE` -- do NOT re-run the script with a manual `> file` redirect (the missed manual redirect is the exact fabrication hole this closes: 44/48 invocations skipped it), and do NOT rely on the inline Bash preview. If no `RESULT_FILE=` receipt appeared (e.g. the script errored before the tee), treat that as a failure to surface to the user, NOT a cue to triage off the preview.
2. **Read `RESULT_FILE` to completion** and produce a complete digest of every finding (id/priority/file:line/the actual claim). Completeness of findings is the objective — account for EVERY finding, not a head/tail sample. You need not hold the raw bytes in context (a very large result would blow the red-zone budget), but you must process every finding.
3. **Emit a read-receipt derived from the actual file** — its line count (`wc -l "${RESULT_FILE}"`) and its last line (`tail -n 1 "${RESULT_FILE}"`) — before triage begins. This may reuse the script's receipt values, but only after you have actually read the file.

The receipt is a deliberate speed-bump / discipline aid, NOT a cryptographic guarantee (it can in principle be produced without reading the middle), so the binding obligation is the complete finding digest in step 2; the receipt is the forcing function. This gate structurally enforces the always-loaded tool-discipline rule (`.claude/rules/tool-discipline.md` — never assert or triage content not seen cleanly); it is the structural form of the read-findings-before-triage lesson.

After the receipt and complete digest are satisfied, present the full findings to the user (this is the point at which findings are first presented -- never before the gate), then assess them:

1. Read the Codex findings and identify which domains they touch (schema, implementation, API, coaching, documentation, UX).
2. Two domain subagents survive -- `api-scout` (GameChanger API archaeology) and `baseball-coach` (coaching semantics). Consult one only when a finding genuinely turns on its domain; don't delegate what a handful of tool calls finishes.

**Assessment is advisory.** It recommends action (fix, defer, dismiss); confirmed findings proceed to Step 5.

### Step 5: Remediation

The session fixes real findings. If all findings were dismissed or marked false positive, skip to Step 6.

For each finding confirmed for remediation:

1. **Validate** it -- confirm it is a real issue, or identify it as a false positive.
2. **Remediate** confirmed issues in the main checkout.
3. Record what changed (files changed and nature of fix).

**Remediation fixes are NOT re-reviewed.** If the user wants another review pass after remediation, they invoke a separate codex-review.

### Step 6: Disposition record

Record every finding with its disposition:

- **FIXED**: with a change summary describing what was fixed (files, nature of change).
- **DISMISSED**: with a reason explaining why the finding was not actionable.
- **FALSE POSITIVE**: with an explanation of why the finding does not apply.

Record them in the chunk's spec file under `.project/specs/`, in its progress log.

### Step 7: Wrap up

Present the disposition summary to the user. Remediation lands through the normal lifecycle: scan, operator approval, commit.

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

**Large removal/refactor chunks**: when the size comes from many DELETED files, re-scope the diff to added/copied/modified/renamed files only (`git diff main --diff-filter=ACMR`) — pure deletions have no content to review and can dominate the byte/line count (E-239: a ~2.57M-char full diff dropped to ~445K under ACMR, clearing Codex's input limit). Deletions are included by default on the staged/unstaged path and in `base`/`commit` modes, so apply ACMR manually when a removal diff is oversized.

### Step 3: Assemble the lean prompt

Build the prompt matching the format used by `scripts/codex-review.sh`. All content is **embedded directly** in the prompt (not referenced by path) so that codex in ephemeral mode can access it without repository file access. Consistent with the headless path, the Bug Pattern Checklist and Security checklist are single-sourced from the two files beside this one -- read each whole and embed it, do NOT re-summarize it:

```
CODE-REVIEW REQUEST

REVIEW RUBRIC
{rubric file contents — read from /workspaces/baseball-crawl/.project/codex-review.md}

BUG PATTERN CHECKLIST
{full contents of /workspaces/baseball-crawl/.claude/skills/codex-review/bug-pattern-checklist.md}

SECURITY CHECKLIST
{full contents of /workspaces/baseball-crawl/.claude/skills/codex-review/security-checklist.md}

CHANGES TO REVIEW (mode: {mode label})
{diff content}

Instructions:
1. Review the changes above against the rubric and both checklists. Follow the Review Priorities in order.
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
  |       Run codex-review.sh <mode> [args]
  |       Read RESULT_FILE to completion, emit receipt, digest every finding
  |       No changes? -> Report and stop
  |       No findings? -> Report clean review, stop
  |       Findings? -> Present them, then assess
  |       Findings confirmed for remediation?
  |         NO -> Stop
  |         YES -> The session validates each finding (real issue or false positive)
  |           and fixes the real ones in the main checkout
  |           Record dispositions (FIXED/DISMISSED/FALSE POSITIVE) in the chunk's spec
  |           Fixes are NOT re-reviewed
  |           Present disposition summary; remediation lands via the normal lifecycle
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
Report the error and stop. Do not attempt to generate a prompt or run the script without the rubric. The script also fails closed if either checklist file beside this one (`bug-pattern-checklist.md`, `security-checklist.md`) is **missing OR empty** -- a truncated-to-zero file and an absent one are the same defect from the prompt's point of view, and the Codex prompt must never ship with a zero or partial security rubric. If that error appears, the fix is to restore the checklist file, not to bypass the read.

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

1. **Do not spawn a subagent to do the review, or to triage its findings.** The session runs both. The only two subagents left are the domain specialists `api-scout` and `baseball-coach`, and they are consulted on a specific domain question, never handed the review.
2. **Do not assess findings in the prompt-generation path.** Assessment is headless-only. The prompt-gen path assembles and presents -- nothing more.
3. **Do not embed rubric content in this skill file.** The rubric is read at runtime and embedded in the generated prompt (both script and prompt-generation paths); it is NOT hardcoded here. Three files are read fresh at prompt-assembly time: `.project/codex-review.md` supplies the Setup, Codex-specific priorities, and Reporting sections, and `bug-pattern-checklist.md` / `security-checklist.md` beside this file supply the two checklists (read whole, so they never drift from what is on disk).
4. **Do not summarize the diff in prompt-generation.** The prompt must contain the complete diff content. Codex needs the full code to perform a meaningful review.
5. **Do not add separator walls, "Begin your response with" instructions, or team recommendation blocks to prompts.** The lean format has no ceremony.
6. **Do not implement fixes while assessing.** Assessment recommends; Step 5 is where the session fixes real findings.
