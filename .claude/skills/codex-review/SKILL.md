---
name: codex-review
description: This skill should be used when the user says "codex review", "review with codex", "codex review E-NNN", "code review", "code review E-NNN", "review epic", "review epic E-NNN", "post-dev review", "codex review prompt", "code review prompt", "generate codex review prompt", or "generate code review prompt" -- or otherwise implies running a Codex code review on implementation changes. The ABSENCE of the word "spec" is the mode discriminator: a review request CONTAINING it belongs to the codex-spec-review skill, not this one. A trigger containing "prompt" selects the prompt-generation path; otherwise the headless path runs.
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

## Epic Worktree Path

When this skill is invoked during the "and review" chain (implement skill Phase 4), the epic worktree path is available from the dispatch context. The implement skill creates the epic worktree in Phase 2 Step 1 at `/tmp/.worktrees/baseball-crawl-E-NNN/` and carries it through the entire dispatch lifecycle. Phase 4 invokes this skill after all stories are DONE but before closure -- the epic worktree contains all accumulated story patches (the complete epic diff against main).

When this skill is invoked standalone (not during dispatch), no epic worktree path is available. The skill operates on the main checkout as before.

---

## Headless Path

### Step 1: Run the script

Run the code review script via Bash in the foreground. When an epic worktree path is available (during the "and review" chain), pass `--workdir <epic-worktree-path>` so that `uncommitted` mode generates the diff from the epic worktree against main:

**During "and review" chain (epic worktree available):**
```
timeout 1200 ./scripts/codex-review.sh --workdir <epic-worktree-path> <mode> [args]
```

**Standalone invocation (no epic worktree):**
```
timeout 1200 ./scripts/codex-review.sh <mode> [args]
```

Examples:
- `timeout 1200 ./scripts/codex-review.sh --workdir /tmp/.worktrees/baseball-crawl-E-137 uncommitted`
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

**Test-sweep caveat**: any test run Codex performs while reviewing is **best-effort** and advisory -- Codex reviews the diff, it is not the test gate. The authoritative full-suite check is the implement skill's Phase 5 Step 1b closure gate (`python -m pytest tests/` against the main checkout). Do not treat a Codex "tests pass" statement as a substitute for that gate, and do not skip Step 1b because Codex ran tests.

### Step 4: Offer advisory triage

**Read-receipt gate — REQUIRED. Triage MUST NOT proceed until this is satisfied.**

The headless script streams Codex's output to the Bash tool result, which is truncated to a *preview* when the result is large. Triaging off that preview is the motivating failure mode: in the E-230 dispatch a triage question was fired off a ~2KB preview of a ~373KB persisted Codex result, mischaracterizing four valid findings as "2 LOW already-adjudicated." Before ANY triage tool or action runs against the review result you MUST:

1. **Locate the script-produced result file.** The script tees the full Codex output to a deterministic file and prints a receipt on stdout: a `RESULT_FILE=<path>` line, that file's `wc -l`, and its `tail -n1`. Read that `RESULT_FILE` -- do NOT re-run the script with a manual `> file` redirect (the missed manual redirect is the exact fabrication hole this closes: 44/48 invocations skipped it), and do NOT rely on the inline Bash preview. If no `RESULT_FILE=` receipt appeared (e.g. the script errored before the tee), treat that as a failure to surface to the user, NOT a cue to triage off the preview.
2. **Read `RESULT_FILE` to completion** and produce a complete digest of every finding (id/priority/file:line/the actual claim). Completeness of findings is the objective — account for EVERY finding, not a head/tail sample. You need not hold the raw bytes in context (a very large result would blow the red-zone budget — see `.claude/skills/context-fundamentals/SKILL.md`), but you must process every finding.
3. **Emit a read-receipt derived from the actual file** — its line count (`wc -l "${RESULT_FILE}"`) and its last line (`tail -n 1 "${RESULT_FILE}"`) — before triage begins. This may reuse the script's receipt values, but only after you have actually read the file.

The receipt is a deliberate speed-bump / discipline aid, NOT a cryptographic guarantee (it can in principle be produced without reading the middle), so the binding obligation is the complete finding digest in step 2; the receipt is the forcing function. This gate structurally enforces the always-loaded output-integrity rule (`.claude/rules/tool-output-integrity.md` — never assert or triage content not seen cleanly) and the clean-reread-before-defect discipline (`.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`); it is the structural form of the read-findings-before-triage lesson.

After the receipt and complete digest are satisfied, present the full findings to the user (this is the point at which findings are first presented -- never before the gate) and offer an advisory triage session:

1. Read the Codex findings and identify which domains they touch (schema, implementation, API, coaching, documentation, agent infrastructure, UX).
2. Map those domains to agents from CLAUDE.md's Agent Ecosystem table (ambient context at runtime -- do NOT use a hardcoded roster).
3. Offer to spawn a triage team with the relevant agents. The team composition depends on the findings' domains -- there is no fixed team.
4. If the user accepts, spawn the relevant agents as named subagents via the `Agent` tool (the triage team forms implicitly on the first spawn). If the user declines, the workflow ends.

**Triage is advisory.** The team assesses findings and recommends action (fix, defer, dismiss) but does NOT implement changes directly. Confirmed findings proceed to Step 5 (Remediation Loop).

### Step 5: Remediation loop

After triage completes (whether via triage team or main session assessment), any findings confirmed for remediation enter the remediation loop. If all findings were dismissed or marked false positive during triage, skip to Step 7. Remediation is authorized by the post-review remediation exception in `workflow-discipline.md`'s Work Authorization Gate -- the codex-review skill does not declare its own authorization model.

**Spawning mechanics** depend on context:

- **(a) "And review" chain** (invoked from implement skill Phase 4): The dispatch team is still active. A fresh implementer is spawned into the **epic worktree** (without `isolation: "worktree"`) using the agent routing table to select the appropriate agent type for each finding's domain. The original dispatch team implementers may have been shut down, so a fresh spawn is the reliable path. PM is already on the team for disposition tracking. See the implement skill's **Remediation Spawn Context** (defined at the start of Phase 5) for the full spawn context.
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

- If this was an "and review" chain, this skill ran as the implement skill's Phase 4 (Codex) pass; control returns to the implement skill, which proceeds to Phase 5 (closure). This Codex pass does not re-run -- but the review chain is NOT complete when this skill returns: the unconditional **Closure CR Integration Review** (Phase 5 Step 1c) still runs, adjudicating the post-Codex-remediation diff before the closure merge. Codex-first is deliberate so that CR sees Codex's findings and the remediation rather than approving-then-reversing.
- If this was a standalone review, present the disposition summary to the user and offer to commit changes.

---

## Prompt-Generation Path

### Step 1: Gather the diff

Use Bash to gather the diff content based on the mode. When an epic worktree path is available (during the "and review" chain), use `git -C <epic-worktree-path>` to run git commands from the epic worktree.

**Mode: `uncommitted`**

**During "and review" chain (epic worktree available):**

Run a single command to get all changes relative to the epic's branch point:
```
git -C <epic-worktree-path> diff $(git -C <epic-worktree-path> merge-base epic/E-NNN main)
```

This produces the complete epic diff (all accumulated story patches). **The base is the MERGE BASE, never bare `main`** -- in the epic worktree `HEAD` is `epic/E-NNN` and `main` moves while the epic runs, so a bare-`main` diff folds main's own post-branch commits into what reads as the epic's work. In E-278 exactly that produced an 85-line phantom finding against a file no story touched.

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

**Large removal/refactor epics**: when the size comes from many DELETED files (a removal epic), re-scope the diff to added/copied/modified/renamed files only (`git diff main --diff-filter=ACMR`) — pure deletions have no content to review and can dominate the byte/line count (E-239: a ~2.57M-char full diff dropped to ~445K under ACMR, clearing Codex's input limit). Note: the script's WORKDIR (epic-worktree) `uncommitted` path already defaults to `--diff-filter=ACMR` for exactly this reason (see `scripts/codex-review.sh`), so during an "and review" chain the headless diff is already deletion-filtered. This prompt-generation guidance therefore applies to the standalone (non-WORKDIR) staged/unstaged path and to `base`/`commit` modes, where deletions are still included by default — apply ACMR manually here when a removal diff is oversized.

### Step 3: Assemble the lean prompt

Build the prompt matching the format used by `scripts/codex-review.sh`. All content is **embedded directly** in the prompt (not referenced by path) so that codex in ephemeral mode can access it without repository file access. Consistent with the headless path, the Bug Pattern Checklist and Security checklist are single-sourced from `code-reviewer.md` -- read the content between the delimiter markers and embed it, do NOT re-summarize it:

```
CODE-REVIEW REQUEST

REVIEW RUBRIC
{rubric file contents — read from /workspaces/baseball-crawl/.project/codex-review.md}

CODE-REVIEWER BUG PATTERN CHECKLIST (single-sourced live from code-reviewer.md)
{content between <!-- BUG-PATTERN-CHECKLIST:START --> and <!-- BUG-PATTERN-CHECKLIST:END --> in /workspaces/baseball-crawl/.claude/agents/code-reviewer.md}

CODE-REVIEWER SECURITY CHECKLIST (single-sourced live from code-reviewer.md)
{content between <!-- SECURITY-CHECKLIST:START --> and <!-- SECURITY-CHECKLIST:END --> in /workspaces/baseball-crawl/.claude/agents/code-reviewer.md}

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
Report the error and stop. Do not attempt to generate a prompt or run the script without the rubric. The script also fails closed if `.claude/agents/code-reviewer.md` is missing or if its checklist delimiters violate the contract it enforces -- each of the four markers (`BUG-PATTERN-CHECKLIST` / `SECURITY-CHECKLIST` START/END) must appear EXACTLY ONCE and each START must precede its END. A duplicated or out-of-order marker fails closed (the single-source extraction requires the contract, and the Codex prompt must never ship with a zero or partial security rubric). If that error appears, the fix is to restore the delimiter contract in `code-reviewer.md`, not to bypass the extraction.

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
3. **Do not embed rubric content in this skill file.** The rubric is read at runtime and embedded in the generated prompt (both script and prompt-generation paths); it is NOT hardcoded here. Two sources are read fresh at prompt-assembly time: `.project/codex-review.md` supplies the Setup, Codex-specific priorities, and Reporting sections, and `.claude/agents/code-reviewer.md` supplies the Bug Pattern Checklist and Security checklist (single-sourced via its delimiter markers, so they never drift from CR's rubric).
4. **Do not summarize the diff in prompt-generation.** The prompt must contain the complete diff content. Codex needs the full code to perform a meaningful review.
5. **Do not add separator walls, "Begin your response with" instructions, or team recommendation blocks to prompts.** The lean format has no ceremony.
6. **Do not implement fixes during triage.** Triage is advisory -- the triage team assesses and recommends but does NOT write code. Implementation happens in the separate remediation phase (Step 5), which is authorized by the post-review remediation exception in `workflow-discipline.md`'s Work Authorization Gate.
