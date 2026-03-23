# Skill: implement

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "implement E-NNN", "implement epic E-NNN"
- "start epic E-NNN", "start E-NNN"
- "execute E-NNN", "execute epic E-NNN"
- "dispatch E-NNN", "dispatch epic E-NNN"
- "run epic E-NNN", "kick off E-NNN"
- "dispatch story E-NNN-SS", "implement story E-NNN-SS", "execute story E-NNN-SS"
- Any request that implies dispatching an epic's stories (or a single story) for implementation

**Chaining modifier**: The user may append "and review" or "and codex review" to any trigger phrase (e.g., "implement E-NNN and review", "start E-NNN and codex review"). This chains a code review after implementation completes. See Phase 4.

**Plan skill handoff**: This skill may also be loaded by the plan skill's Phase 5 when the user used a compound trigger ("plan and dispatch"). In this case, `handoff_from_plan = true` and a planning team is already active. The implement skill reuses the existing team rather than creating a fresh one. See Phase 1 and Phase 2 for handoff-specific paths.

---

## Purpose

Codify the full workflow for dispatching and coordinating an epic when the user requests implementation. The main session (user-facing agent) is the spawner and router: it reads the epic, creates an epic worktree, spawns implementers, code-reviewer, and PM (all working in the epic worktree), assigns stories serially, routes completion reports through review and AC verification, manages the staging boundary between stories, and runs the closure sequence (merge epic worktree to main, commit, cleanup). The main session does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git worktree add/remove` for epic worktree lifecycle, `git diff`/`git apply` for closure merge to main, `git add -A` for staging boundary and closure commit, `git commit` for the closure commit, `git branch -D` for branch cleanup, `git mv` for archival) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

**Enforcement model**: A PreToolUse hook (`.claude/hooks/worktree-guard.sh`) blocks Write and Edit operations to implementation paths (`src/`, `tests/`, `migrations/`, `scripts/`) when the target is the main checkout. This provides deterministic enforcement that implementation work happens in worktrees. The hook is the primary mechanism; instruction-based constraints in this skill are backup for edge cases the hook cannot cover (e.g., Bash file writes).

When invoked via plan skill handoff (`handoff_from_plan = true`), the planning team is already active with PM and domain experts. The implement skill reuses these agents rather than creating a fresh team, preserving expert context from the planning session (unified team lifecycle).

This skill is the authoritative source for dispatch procedures. Agent routing tables are in `/.claude/rules/agent-routing.md`. See `/.claude/rules/dispatch-pattern.md` for a brief overview of dispatch roles.

---

## Prerequisites

Before dispatch, verify:

1. **The target epic exists.** Check that `/epics/E-NNN-slug/epic.md` exists. If not found, search `/epics/` for a directory starting with `E-NNN`. If no match, report to the user: "Epic E-NNN not found in `/epics/`." and stop.

2. **The epic status is `READY` or `ACTIVE`.** Read the epic file and check the `## Status` section.
   - If `READY` or `ACTIVE`: proceed.
   - If `DRAFT`: refuse. Tell the user: "Epic E-NNN is in DRAFT status. It must be marked READY after refinement is complete before it can be dispatched."
   - If `COMPLETED`: refuse. Tell the user: "Epic E-NNN is already COMPLETED."
   - If `ABANDONED`: refuse. Tell the user: "Epic E-NNN has been ABANDONED."
   - If `BLOCKED`: report the blocked status and any blocking details to the user. Do not proceed.

---

## Phase 0: tmux Window Rename

If the session is running inside tmux, rename the current window to the epic ID and dispatch stage for easy identification during Heavy mode dispatch. Run this via the Bash tool **before** team creation begins.

**Command** (substitute the actual parsed epic ID for the placeholder -- e.g., `"E-090 dispatch"`, not the literal string `"E-NNN dispatch"`):

```bash
{ [ -n "$TMUX" ] && command -v tmux >/dev/null 2>&1 && tmux rename-window "E-NNN dispatch" 2>/dev/null; } || true
```

This step is completely silent and non-blocking:
- If `$TMUX` is not set (not in tmux), the guard short-circuits before invoking `tmux`.
- If the `tmux` binary is not on PATH, the second guard short-circuits.
- If `tmux rename-window` fails at runtime (stale socket, permission error), stderr is suppressed via `2>/dev/null`.
- The trailing `|| true` guarantees exit code 0 on all paths.

Do not report the result to the user or treat a failure as an error. Proceed to Phase 1 regardless.

---

## Phase 1: Team Composition

**If `handoff_from_plan = true`** (plan skill handoff): The planning team is already active with PM and domain experts. The plan skill has already performed the team transition (PM role change, consultation-mode agents transitioned to implementation mode, code-reviewer either reused from plan Phase 3 or spawned fresh during handoff). Skip the team composition analysis below and proceed to Phase 2, which will detect the handoff and skip team/agent creation.

**If `handoff_from_plan = false`** (standard dispatch): Read the epic's `## Dispatch Team` section.

- **If present and non-empty**: Extract the listed agent types. These are the implementers to spawn. PM and code-reviewer are always spawned as infrastructure -- they are not listed in the Dispatch Team section.
- **If absent or empty**: Use the Agent Selection routing table in `/.claude/rules/agent-routing.md` to determine which agent types are needed based on story domains and "Files to Create or Modify" sections. Read story files to make this determination.

---

## Phase 2: Dispatch

**If `handoff_from_plan = true`** (plan skill handoff): The planning team is already active, the epic worktree was created by the plan skill's handoff sequence, and agents have been transitioned. Skip Steps 1-3 (epic worktree creation, team creation, agent spawning). Proceed directly to Step 4 (set epic to ACTIVE). Code-reviewer is already on the team -- either spawned during the plan skill's Phase 3 (internal review cycle) and transitioned to code-review mode, or spawned fresh during Phase 5 Step 3a if Phase 3 was skipped. Do not re-spawn it. If any additional implementer types are needed that were not on the planning team, spawn them now using the universal spawn context below.

**If `handoff_from_plan = false`** (standard dispatch): Create the epic worktree, the team, and spawn all agents as described below.

### Step 1: Create the epic worktree

Before team creation, create an epic-level worktree where all agents work during dispatch.

**Command** (substitute the actual epic ID):

```bash
git worktree add -b epic/E-NNN /tmp/.worktrees/baseball-crawl-E-NNN
```

- **Path**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (e.g., `/tmp/.worktrees/baseball-crawl-E-137/`)
- **Branch**: `epic/E-NNN` (e.g., `epic/E-137`)
- Store the epic worktree path for use throughout dispatch -- all agents receive it in their spawn context.

If the branch or worktree already exists (e.g., resuming a previously interrupted dispatch), reuse the existing worktree rather than failing.

### Step 2: Create the team

Use `TeamCreate` to create a dispatch team for the epic.

### Step 3: Spawn implementing agents, code-reviewer, and PM

All agents are spawned WITHOUT `isolation: "worktree"` and receive the epic worktree path in their spawn context. They use absolute paths under the epic worktree for all file operations.

**Universal implementer spawn context:**

```
You are a [agent-type] agent on the [team-name] team. Wait for the main session to assign you a story via SendMessage. Do not begin work until you receive your story assignment with the full story file text and Technical Notes.

Your working directory for all file operations: [epic-worktree-path]
(e.g., /tmp/.worktrees/baseball-crawl-E-NNN/)

Use absolute paths under this directory for ALL file reads, writes, and git commands.
```

**Spawn the code-reviewer** alongside the implementing agents. The code-reviewer is infrastructure, not a story-specific implementer -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. Code-reviewer spawn context:

```
You are the code-reviewer agent on the [team-name] team. Wait for review assignments from the main session via SendMessage. Do not self-initiate reviews. Each review assignment will include a story ID, the full story file text, epic Technical Notes, and the implementer's Files Changed list.

Epic worktree path: [epic-worktree-path]
All story work happens in this worktree. Use it when reading files and running git diff.
Review the current story's changes via `cd [epic-worktree-path] && git diff` (unstaged changes = current story).
Review all accumulated changes via `cd [epic-worktree-path] && git diff --cached main` (staged = prior stories).
```

**Spawn the product-manager (PM)** alongside implementers and code-reviewer. PM is infrastructure -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. PM spawn context:

```
You are the product-manager agent on the [team-name] team. Your role during dispatch is status management and AC verification. You own: story status file updates (TODO -> IN_PROGRESS -> DONE), epic Stories table updates, epic status transitions (READY -> ACTIVE -> COMPLETED), and AC verification ("did they build what was specified"). Wait for routing from the main session via SendMessage -- the main session will send you status update requests and completion reports for AC verification. Do not self-initiate work.

Epic file: [absolute path to epic.md in epic worktree]
Epic worktree path: [epic-worktree-path]
All story work happens in this worktree. Use absolute paths under the epic worktree for all file operations (story files, epic files, status updates).
```

**PM context window recovery**: If PM's context fills during large epics, the main session respawns PM with a fresh summary of current epic state: which stories are DONE, which are IN_PROGRESS, and a reminder of PM's role. No state is lost because PM's work products (status files, epic table) persist on disk.

### Step 4: Set epic to ACTIVE

If this is the first dispatch of this epic (status is `READY`), route to PM to update the epic status to `ACTIVE`.

---

## Phase 3: Coordination

The main session routes work during dispatch. PM owns statuses and AC verification. Stories execute **serially** -- one story at a time. This is the core dispatch loop.

### Step 1: Identify next eligible story

Find the next story with `Status: TODO` whose blocking dependencies are all `DONE`. If multiple stories are eligible, pick the first one by story number (E-NNN-01 before E-NNN-02).

### Step 2: Route story to agent

For the eligible story:

1. **Check Agent Hint.** If the story has an `## Agent Hint` field, prefer that agent type.
2. **Check context-layer routing.** Scan the story's "Files to Create or Modify" section. If **any** file matches a context-layer path (see Routing Precedence in `/.claude/rules/agent-routing.md`), that story MUST go to `claude-architect` regardless of the Agent Hint.
3. **Fall back to routing table.** If no Agent Hint and no context-layer match, use the Agent Selection table in `/.claude/rules/agent-routing.md` to determine the agent type from file paths and story domain.

All stories are executed in the epic worktree. There is no isolation decision branch.

### Step 3: Update statuses

Route to PM to mark the story `IN_PROGRESS` in both the story file and the epic Stories table.

### Step 4: Assign story to implementer

Send the implementer the story via `SendMessage` with a full context block:

```
You are executing story E-NNN-SS: [Story Title]

Story file: [epic-worktree-path]/epics/E-NNN-slug/E-NNN-SS.md

[Full contents of the story file]

Context from parent epic Technical Notes:
[Full Technical Notes section from epic.md]

Completed dependencies:
- E-NNN-01: [title] -- DONE
Handoff context from completed dependencies:
- From E-NNN-01: [artifact path and description from upstream story's Handoff Context section]

You are working in the epic worktree at: [epic-worktree-path]
Use ABSOLUTE PATHS under this directory for ALL file operations.

## Epic Worktree Constraints

**Enforcement**: A PreToolUse hook blocks Write/Edit to `src/`, `tests/`, `migrations/`, `scripts/` in the main checkout. You are in the epic worktree, so your writes pass. Do NOT use main-checkout paths.

**Prohibited:**
- Bash file writes (`echo >`, `sed -i`, `cat >`, `cp`, `mv`) to `src/`, `tests/`, `migrations/`, `scripts/` -- use Write/Edit tools instead (hook-covered, reviewable diffs)
- `docker compose`, `curl localhost:8001`, app health checks (Docker reads from main, not worktree)
- `bb data *`, `bb creds *`, `bb db *`, `bb status`, `bb proxy *`, `./scripts/proxy-*.sh` (assume main checkout)
- Reading `.env` or `data/` (gitignored, do not exist in worktree)
- `git commit`, `git merge`, `git rebase`, `git worktree remove`, `git branch -d/-D`
- `cd /workspaces/baseball-crawl` -- stay in the epic worktree

**Pytest limitation**: pytest tests the **main checkout's** code (not worktree changes) due to the editable install's meta path finder. Run tests for verification but understand this. Report results in your completion message.

**Permitted**: `git status/diff/log` from worktree. `git diff` = your unstaged changes (this story). `git diff --cached main` = prior stories' staged changes. Edit files via Write/Edit tools with absolute worktree paths.

**Completion**: Report with `## Files Changed` (absolute worktree paths, e.g., `[epic-worktree-path]/src/foo.py (modified)`), `## Test Results` (command, pass/fail, failures), and `## Behavioral Changes`. The Behavioral Changes section is ALWAYS present. List any function whose signature, return type, raised exceptions, or documented side effects changed. Internal refactors that preserve the function's contract are NOT behavioral changes. Format: `- \`function_name()\` in \`file.py\`: [what changed]`. Write "None" when no behavioral changes occurred -- this makes it explicit that you considered the question. This section supplements (does not replace) the code-reviewer's own caller audit -- CR still independently scans the diff for non-obvious behavioral changes. Do NOT run `git add -A` (main session manages staging). Do not modify story status files or epic tables.
```

**Context block requirements**: Include the full story file text and full Technical Notes verbatim (never summarize). Include Handoff Context from completed upstream dependencies.

### Step 5: Monitor, review, and verify

> **Boundary reminder:** If you are about to read source files, run `git log`, `grep`, or inspect the implementation to "quickly check" something -- stop. That is domain work regardless of size, and it must be routed to the appropriate agent. Route it through the review/verification sequence below (see Domain Work During Dispatch in `dispatch-pattern.md`).

When the implementer reports completion (with `## Files Changed`):

**Post-story path verification**: Check every file path in the implementer's `## Files Changed` section. Every path MUST start with the epic worktree pattern (`/tmp/.worktrees/baseball-crawl-E-NNN/`). If any path starts with `/workspaces/baseball-crawl/` (main checkout) or any other unexpected prefix, STOP and escalate to the user before proceeding. This catches agents that accidentally worked in the wrong directory.

1. **Check context-layer-only skip condition.** If the story modifies ONLY context-layer files (`.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/`, `CLAUDE.md`) and no Python code, route to PM for AC verification and status update. The code-reviewer is skipped for context-layer-only stories -- PM verifies ACs alone. After PM confirms ACs pass, proceed to the staging boundary (Step 5a). If PM rejects ACs, route feedback to the implementer for revision.

2. **Route code stories to the code-reviewer AND PM.** For stories that touch Python code or any non-context-layer files, send the work to both in parallel. Code-reviewer template:

```
Review story E-NNN-SS: [Title]
Story file: [epic-worktree-path]/epics/E-NNN-slug/E-NNN-SS.md
[Full story file text]
Epic Technical Notes: [Full Technical Notes]
Epic worktree path: [epic-worktree-path]
Review via `cd [epic-worktree-path] && git diff` (unstaged = this story). Do NOT run pytest -- verify through file inspection.
Implementer files changed: [Files Changed section]
Implementer test results: [Test Results section]
[If applicable] ## API Endpoints Touched
[List of docs/api/endpoints/*.md files -- include when Files Changed or Files to Create or Modify contains paths under src/gamechanger/crawlers/, src/gamechanger/loaders/, src/gamechanger/client.py, or src/pipeline/. Derive specific endpoint docs from the story description/Technical Approach. If specific endpoints cannot be determined, include all docs/api/endpoints/*.md files. Omit this section entirely when no API-touching files are involved. See TN-4a heuristics.]
[If applicable] ## Migration Files
[List of migrations/*.sql files -- include when Files Changed or Files to Create or Modify contains paths under src/api/, src/gamechanger/loaders/, src/db/, src/pipeline/, migrations/, or templates referencing database columns. Omit this section entirely when no database code is involved. See TN-4a heuristics.]
[If applicable] ## Behavioral Changes
[From implementer's completion report. List of functions whose signature, return type, or observable behavior changed. This supplements CR's own caller audit -- CR still independently scans the diff for non-obvious behavioral changes the implementer may not have recognized. Omit this section when the implementer declared "None."]
Review round: 1 of 2 (circuit breaker)
Review against all ACs and the review rubric. Cross-reference Files Changed against "Files to Create or Modify" to flag missing/unexpected files.
```

**Derivation heuristics for structured context fields** (TN-4a): The main session uses these rules to decide which optional context sections to include in the CR assignment. Check both the story's "Files to Create or Modify" and the implementer's Files Changed list:

- **API Endpoints Touched**: Include when any file is under `src/gamechanger/crawlers/`, `src/gamechanger/loaders/`, `src/gamechanger/client.py`, or `src/pipeline/` (modules that parse API responses, make HTTP calls, or orchestrate API-dependent pipelines). `src/gamechanger/config.py`, `src/gamechanger/types.py`, and similar utility modules do NOT trigger this field. Derive specific endpoint docs from the story's Technical Approach or description (e.g., if the story mentions "public team endpoint," include `docs/api/endpoints/get-public-teams-public_id.md`). If specific endpoints cannot be determined, include all files matching `docs/api/endpoints/*.md`.
- **Migration Files**: Include when any file is under `src/api/`, `src/gamechanger/loaders/`, `src/db/`, `src/pipeline/`, `migrations/`, or templates referencing database columns.
- **Behavioral Changes**: Include when the implementer's completion report contains a `## Behavioral Changes` section with content other than "None." Omit when the implementer declared "None."

3. **Triage ALL findings.** Before any routing decision, the main session classifies every finding (MUST FIX and SHOULD FIX) as **valid** or **invalid**:
   - **Valid finding** (correct analysis of the code): Route to the implementer for fixing, regardless of severity (MUST FIX or SHOULD FIX), size, or cosmetic nature. "Correct but too small to fix" is NOT a valid dismissal reason.
   - **Invalid finding** (false positive, misunderstanding of the code, or targets code not modified by the story): Dismiss with explanation. No user confirmation needed.

   The distinction between MUST FIX and SHOULD FIX is preserved in the code-reviewer's output (it signals severity), but the handling for all valid findings is the same: fix it. Every finding reaches a terminal state during the story: FIXED or DISMISSED. No deferral path exists.

4. **If the reviewer returns APPROVED and PM verifies ACs pass** (no MUST FIX findings, ACs satisfied): Triage any SHOULD FIX findings per step 3 above. If all findings are invalid (dismissed) or there are none, proceed to the staging boundary (Step 5a), then route to PM to mark the story `DONE`. If any valid findings exist, route them to the implementer before the staging boundary. After the implementer fixes them, send the updated work back to the reviewer for re-review. The main session routes findings to implementers for resolution -- it NEVER creates, modifies, or deletes any file itself.

   **If PM rejects ACs** (regardless of reviewer verdict): Route PM's AC feedback to the implementer alongside any valid code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. See Gate Interaction below.

   **PM-Reviewer AC Disagreement**: PM can override AC-related MUST FIX items (remove them from the valid findings list). Non-AC findings (bugs, security, conventions) are the reviewer's exclusive domain -- PM cannot override. If removing AC items empties the list, the story passes. PM fail always routes feedback to implementer regardless of reviewer verdict.

5. **If the reviewer returns NOT APPROVED** (MUST FIX findings): Triage all findings per step 3 above. Route all valid findings to the implementer with "Round 1 of 2 -- items to fix below." The implementer fixes in the epic worktree and reports again. Send updated work to the reviewer for Round 2 using the same template as round 1, adding: the round 1 findings verbatim, updated Files Changed and Test Results (annotating which files are new or changed in the remediation vs. carried forward from Round 1, so CR can focus the remediation regression guard on the new/changed files), updated Behavioral Changes from the implementer's revised completion report, the same structured context sections (API Endpoints Touched, Migration Files) from Round 1, and "Review round: 2 of 2 (circuit breaker)" with instructions to focus on whether round 1 findings are resolved and whether fixes introduced new issues.

6. **Circuit breaker.** Max 2 review rounds per story. If the 2nd review still has MUST FIX findings, escalate to the user with the findings summary and present options:
   - (a) Fix it themselves
   - (b) Tell the implementer to try again (resets the circuit breaker)
   - (c) Override the reviewer and proceed to staging boundary + PM closure (explicit user override)
   - (d) Abandon the story
   The main session does NOT mark the story DONE and does NOT loop further without user direction.

### Gate Interaction

When PM rejects ACs, route PM's feedback to the implementer alongside any code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. PM AC rejection does NOT have its own circuit breaker -- the code-reviewer's 2-round circuit breaker governs the overall loop. If the circuit breaker fires, escalate to the user regardless of PM AC status.

### Step 5a: Staging boundary

After both the code-reviewer approves and PM verifies ACs pass for a story (or PM alone approves for context-layer-only stories), the main session runs the staging boundary protocol:

1. **Stage the story's changes**: `cd <epic-worktree-path> && git add -A`
2. This story's changes are now staged. The next story starts with a clean unstaged diff.
3. Route to PM to mark the story `DONE`.

The staging boundary is the inter-story isolation mechanism. After staging:
- `git diff` (unstaged) shows only the next story's changes
- `git diff --cached main` shows the cumulative view (all completed stories)

### Step 6: Cascade

After PM marks a story DONE, check for newly unblocked stories (stories whose blocking dependencies are now all DONE).

- If more stories are eligible, assign the next one (repeat from Step 1 -- serial execution).
- If a new agent type is needed, spawn the agent using the universal spawn context.
- If no more stories are eligible and some are still in progress, wait for completions.
- If all stories are DONE, proceed to Phase 4 (if "and review" modifier was specified) or Phase 5 (if not).

---

## Phase 4: Optional Review Chain

If the user specified the "and review" modifier (e.g., "implement E-NNN and review"), run Phase 4a (CR integration review) followed by Phase 4b (Codex code review). If the modifier was not specified, skip this phase and proceed directly to Phase 5.

### Phase 4a: Code-Reviewer Integration Review

After all stories are verified DONE, Phase 4a runs a holistic code-reviewer pass over the full epic diff. Per-story CR (Phase 3) reviews changes in isolation; the integration review catches cross-story interactions, naming inconsistencies, import conflicts, and architectural issues that only appear when stories are combined.

Phase 4a is skipped if the "and review" modifier was not specified.

#### Step 1: Generate the full epic diff

Run from the epic worktree:

```
cd <epic-worktree-path> && git diff main
```

If the diff is empty (no changes relative to main), report "No changes in epic worktree to review" and skip to Phase 5.

#### Step 2: Build the story manifest

Assemble a story manifest from the epic's Stories table: list each story ID, title, and a one-line summary of what it implemented (drawn from the story's Description or the implementer's completion report). This gives the code-reviewer cross-story context without requiring it to read every story file.

#### Step 3: Route to code-reviewer

Send the integration review assignment to the code-reviewer via `SendMessage` with: the epic worktree path, story manifest (IDs, titles, one-line summaries), full Technical Notes, Goals and Success Criteria, and the full epic diff (from Step 1). Include "Review round: 1 of 2 (circuit breaker)" and instructions to focus on cross-story interactions, naming consistency, import conflicts, and architectural issues.

**Large epic handling**: If the diff exceeds ~3,000 lines, replace inline diff with a per-story file summary (file paths, modified/new status, +/- line counts). Generate from cross-referencing each story's `## Files Changed` with `git diff --stat main`. The reviewer can request specific file contents from the main session.

#### Step 4: Triage, remediation, and circuit breaker

Triage findings using the same rules as Phase 3 Step 5 item 3. Remediate valid findings **one at a time** (serial, not parallel). For each finding: spawn an implementer, wait for completion, stage with `git add -A`, then proceed to the next finding. Select agent type via the routing table. Spawn WITHOUT `isolation: "worktree"`. Provide the **remediation spawn context**:

```
You are a [agent-type] agent spawned for post-review remediation on the [team-name] team.
Working directory: <epic-worktree-path> -- use absolute paths for ALL file operations.
Constraints: no git commit (git add -A only), no docker/bb/proxy commands, no .env/data/ access, no git merge/rebase/worktree/branch commands, no Bash file writes (echo/sed/cat/cp/mv) to src/tests/migrations/scripts/ -- use Write/Edit tools.
Remediation authorized by post-review remediation exception in workflow-discipline.md.
Finding to remediate: [finding details]
Fix and report with ## Files Changed (absolute paths) and ## Test Results.
```

PM records dispositions. If NOT APPROVED, send Round 2 to the code-reviewer with round 1 findings and updated diff. Max 2 rounds -- if round 2 still has MUST FIX, escalate to the user: (a) fix, (b) retry (resets breaker), (c) override to Phase 4b, (d) abandon.

After integration review completes (clean, remediated, or user override), proceed to Phase 4b.

### Phase 4b: Codex Code Review

After Phase 4a completes (whether CR findings were remediated, the review was clean, or it was skipped), Phase 4b runs a Codex review against the epic worktree diff as a systematic final validation pass. This uses a degradation chain: headless first, prompt-generation fallback on failure.

Phase 4b is skipped if the "and review" modifier was not specified.

#### Step 1: Attempt headless codex review

Run the codex-review script with the epic worktree path via Bash:

```
timeout 600 ./scripts/codex-review.sh --workdir <epic-worktree-path> uncommitted
```

Capture the exit code and output.

#### Step 2: Evaluate the result

- **Exit 0, output contains "No findings."** (clean review): Report "Codex review completed with no findings -- clean review" to the user. Skip to Phase 5.

- **Exit 0, output contains findings**: Proceed to Step 3 (triage and remediation).

- **Exit 124 (timeout)**: Fall to Step 4 (prompt-generation fallback). The pause message is:
  > Pipeline paused at codex review. Headless review timed out. Run this prompt async and paste findings when ready. Enter 'skip' to proceed without codex review.

- **Other non-zero exit** (codex not installed, script error, API outage): Fall to Step 4 (prompt-generation fallback). The pause message is:
  > Pipeline paused at codex review. Headless review failed: [error message from script]. Run this prompt async and paste findings when ready. Enter 'skip' to proceed without codex review.

- **Exit 0, output contains "No uncommitted changes to review"**: Report this to the user and skip to Phase 5.

#### Step 3: Triage and remediation (headless findings)

When headless codex succeeds with findings:

1. Present the full codex findings to the user.
2. Classify each finding as **valid** or **invalid** using the same triage rules as Phase 3 Step 5 item 3.
3. Remediate valid findings using the same spawn mechanics as Phase 4a Step 4 (remediation spawn context). Stage fixes with `git add -A`.
4. PM records dispositions in the epic's History section.
5. **Remediation fixes are NOT re-reviewed**. After remediation, proceed to Phase 5.
6. **Circuit breaker (2 rounds)**: If round 2 still has unresolved findings, escalate to the user: (a) fix it themselves, (b) retry (resets breaker), (c) override and proceed to Phase 5, (d) abandon.

#### Step 4: Prompt-generation fallback (graceful degradation)

When headless codex times out or fails: generate a review prompt using the codex-review skill's prompt-generation path (`.claude/skills/codex-review/SKILL.md`, Steps 1-3) with the epic worktree diff. Present the pause message + prompt to the user. Wait for: "no findings" (clean, skip to Phase 5), pasted findings (enter Step 3 triage), or "skip" (advance to Phase 5 without findings).

After Codex review completes (clean, remediated, skipped, or user override), proceed to Phase 5.

---

## Phase 5: Closure Sequence

**Phase boundary**: Phase 4 handles all review and remediation logic. Phase 5 handles all closure mechanics (status updates, assessments, commit, archive). No review logic belongs in Phase 5.

When all stories are verified DONE (and the optional review chain is complete), execute the following closure sequence in order.

**Before spinning down the team:**

### Step 1: Validate all work

Confirm all stories are DONE. Per-story AC verification was performed by PM during Phase 3 (for all stories), and code quality was verified by the code-reviewer (for code stories). This step confirms completion status -- it is not a re-review.

### Step 2: Update the epic completely

Route to PM, who performs:

- Confirm all story file statuses are DONE.
- Epic Stories table reflects current reality (all rows DONE).
- Epic status updated to COMPLETED.
- History entry added with the completion date and a summary of what was accomplished.
- Record a review scorecard table in the epic's History section using this format:

```
### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-NNN-01 | N | N | N |
| Per-story CR -- E-NNN-02 | N | N | N |
| CR integration review | N | N | N |
| Codex code review | N | N | N |
| **Total** | **N** | **N** | **N** |
```

Only include rows for review passes that actually ran. Per-story CR rows show aggregated finding totals across all review rounds for that story (e.g., if round 1 had 3 MUST FIX and round 2 had 1, the row shows 4 findings total). CR integration and Codex rows show findings from Phase 4a and 4b respectively. If the "and review" modifier was not specified, omit Phase 4 rows. Reconstruct finding counts from triage summaries recorded during each story's review loop and Phase 4 reviews.

- Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information out of epic files.

### Step 3: Documentation assessment

Per `.claude/rules/documentation.md`. If any trigger fires, spawn docs-writer before archiving. Otherwise record "No documentation impact."

### Step 3a: Context-layer assessment

Per `.claude/rules/context-layer-assessment.md`. Six triggers, explicit yes/no verdicts in epic History. If any fires, spawn claude-architect before archiving.

### Step 4: Review ideas backlog

PM checks `/.project/ideas/README.md` for CANDIDATE ideas unblocked by epic completion.

### Step 5: Review vision signals

PM checks `docs/vision-signals.md` for unprocessed signals. Advisory, not blocking.

### Step 6: Present a summary to the user

Before closure merge: epic ID/title, stories completed, review outcomes (per-story CR: N stories reviewed; CR integration: clean/N fixed/not run; Codex: clean/N fixed/skipped/not run), file list (`git diff --stat main` from epic worktree), key artifacts, follow-up work, promotable ideas.

### Step 7: Shut down implementers and code-reviewer

Send a `shutdown_request` to each implementer and to the code-reviewer. Wait for shutdown confirmations. **Do NOT shut down PM yet** -- PM is needed for memory updates after archive.

**After spinning down implementers and code-reviewer:**

### Step 7a: Ancillary file sweep

Stage any main-checkout session artifacts before the closure merge. During dispatch, agents write to the epic worktree (those changes are captured by Step 8's worktree patch). This step stages main-checkout changes: vision signals from the main session, leftover planning artifacts, or idea captures. These staged files are included in Step 8's closure commit alongside the worktree patch -- no separate commit is made here, because committing on main would advance HEAD and cause Step 8's `git diff --cached main` to generate reverse patches for the committed files.

**Preflight**: Run `cd /workspaces/baseball-crawl && git status --porcelain` (without `-uall`). If the output is empty, skip this step silently and proceed to Step 8.

**Enumerate main-checkout changes**: Use the TN-8 approach to identify ancillary artifacts:

1. **Recognized artifact paths** (stage these):
   - `docs/vision-signals.md` (if modified) -- single file, `git add docs/vision-signals.md`
   - `.claude/agent-memory/` (leftover planning artifacts not committed by plan skill Step 2a, if any) -- mixed directory, enumerate with:
     ```
     git diff --name-only -- .claude/agent-memory/
     git ls-files --others --exclude-standard -- .claude/agent-memory/
     ```
     Stage each matching file individually with `git add <file>`.
   - `.project/ideas/` (if any ideas captured by the main session during dispatch) -- mixed directory, enumerate with:
     ```
     git diff --name-only -- .project/ideas/
     git ls-files --others --exclude-standard -- .project/ideas/
     ```
     Stage each matching file individually with `git add <file>`.

2. **Classification**: Files matching recognized patterns above are staged. Files NOT matching any recognized pattern are **unrecognized** -- report them to the user and wait for instructions before proceeding. Do not stage unrecognized files automatically.

**Present staged changes**: After staging recognized files, run `git diff --cached --stat` and present the summary to the user.

**User approval**: Require explicit approval before staging is finalized. Only "yes", "approve", "go ahead" proceed.

**User rejects**: Pause and wait for instructions. The user can:
- (a) Adjust staged files and retry (e.g., unstage something with `git reset HEAD <file>`)
- (b) Inspect staged changes (`git diff --cached`)
- (c) Skip (unstage all with `git reset HEAD`, proceed to Step 8 -- the clean-tree preflight will catch remaining changes)

### Step 8: Closure merge and commit

Merge the epic worktree's accumulated changes into the main checkout and produce a single commit.

**Migration merge-time scan:** If the epic includes new migrations AND main has added migrations since the worktree branched, flag the numbering conflict to the user before proceeding.

**Clean-tree preflight:** Before starting the merge, verify the main checkout has no unstaged or untracked changes. Step 7a may have legitimately staged ancillary files, so check unstaged/untracked only:
```
cd /workspaces/baseball-crawl && git diff --name-only     # unstaged modifications
cd /workspaces/baseball-crawl && git ls-files --others --exclude-standard  # untracked files
```
If either command produces output, report the unexpected changes to the user and wait for instructions before proceeding. Do NOT proceed with `git apply` on a dirty working tree -- it may silently merge unrelated changes into the epic commit. Staged files from Step 7a are expected and will be captured in the closure commit.

**Closure merge sequence:**

1. `cd <epic-worktree-path> && git add -A` (stage all accumulated changes)
2. `cd <epic-worktree-path> && git diff --binary --cached main > /tmp/E-NNN-epic.patch`
3. `cd /workspaces/baseball-crawl && git apply --check --3way /tmp/E-NNN-epic.patch` (dry-run)
4. If dry-run succeeds: `git apply --3way /tmp/E-NNN-epic.patch` (apply for real)
5. PII scan (pre-commit hook covers this automatically)
6. `git add -A`, present staged changes, ask for explicit user approval
7. `git commit -m "feat(E-NNN): <epic title>"`
8. `git worktree remove <epic-worktree-path> && git branch -D epic/E-NNN`

**Dry-run fails**: Present conflict report. User decides: (a) resolve manually and retry, or (b) abort (worktree preserved).

**User must explicitly approve** before commit. Only "yes", "commit", "approve", "go ahead" proceed.

**If the user rejects the commit**: Pause. Epic worktree preserved. User can: (a) 'commit' to resume, (b) inspect, or (c) 'abort' (worktree preserved for manual recovery). If PII scan catches issues, nothing is committed.

### Step 9: Archive the epic

`git mv epics/E-NNN-slug/ .project/archive/E-NNN-slug/`. Verify fully staged via `git status --porcelain` (stage any unstaged archive-related changes before proceeding).

### Step 10: Update PM memory

PM moves epic from "Active Epics" to "Archived Epics" in `.claude/agent-memory/product-manager/MEMORY.md`.

### Step 11: Archive commit

`git add -A && git commit -m "chore(E-NNN): archive epic"`.

### Step 12: Shut down PM and delete team

Shutdown PM, wait for confirmation, delete team.

---

## Workflow Summary

```
Prerequisites -> Phase 0 (tmux) -> Phase 1 (team composition) -> Phase 2 (dispatch setup)
  |
  v
Phase 2: Create epic worktree -> create team -> spawn agents (all in epic worktree, no isolation) -> PM sets ACTIVE
  (handoff_from_plan: skip Steps 1-3, reuse existing team + worktree)
  |
  v
Phase 3: Serial coordination loop (one story at a time)
  Pick next eligible -> route to agent -> PM marks IN_PROGRESS -> assign with context block
  -> implementer works in epic worktree -> reports ## Files Changed
  -> post-story path verification (must match epic worktree pattern)
  -> context-layer-only? PM verifies ACs alone : code-reviewer + PM in parallel
  -> triage findings (valid=fix, invalid=dismiss) -> 2-round circuit breaker
  -> staging boundary: `git add -A` -> PM marks DONE -> cascade to next story
  |
  v
Phase 4 (if "and review"): 4a CR integration review + 4b Codex code review (headless -> prompt fallback)
  Both use triage + remediation in epic worktree, 2-round circuit breakers
  |
  v
Phase 5: Validate -> PM completes epic -> doc + context-layer assessments -> summary
  -> shut down implementers + CR -> ancillary file sweep (stage session artifacts, user approval)
  -> closure merge (patch -> dry-run -> apply -> single commit incl. ancillary files)
  -> archive -> PM memory -> archive commit -> shut down PM + delete team
```

---

## Edge Cases

- **Epic not found / DRAFT / COMPLETED / ABANDONED / BLOCKED**: Report status to user and stop. Do not search the archive for completed epics.
- **No eligible stories**: Report to user (all BLOCKED or all DONE).
- **Spawn fails**: Follow Dispatch Failure Protocol (`workflow-discipline.md`) -- report and ask, do not improvise.
- **No uncommitted changes for review**: Phase 4a handles (skip to Phase 5 -- if no diff for CR, Codex also has nothing to review).
- **Codex timeout/failure**: Phase 4b degrades to prompt-generation fallback.
- **CR or PM context fills**: Respawn with fresh state summary. No data lost (work products persist on disk).

---

## Anti-Patterns

1. **Do not fall for the "quick check" trap.** The main session MUST NOT: create, modify, or delete any file; verify ACs or update statuses; bypass the code-reviewer; absorb a crashed agent's work; apply fixes -- not even trivial one-line fixes. When something feels too small to route, route it anyway.
2. **Do not summarize context blocks.** Always send the full story file text and full Technical Notes verbatim.
3. **Do not proceed to closure with unverified stories.** If any AC is unmet, send the implementer back.
4. **Do not skip the documentation assessment.** The epic cannot be archived until documentation impact is evaluated.
5. **Do not commit automatically.** The user must explicitly approve the closure commit.
6. **Do not skip PM spawning.** PM handles all status updates and AC verification during dispatch.
7. **Do not skip the context-layer assessment.** The epic cannot be archived until context-layer impact is evaluated.
8. **Do not defer findings to epic History.** Every finding must reach a terminal state (FIXED or DISMISSED) during the story. No deferral path exists.
9. **Do not dismiss valid findings based on size or cosmetic nature.** If the finding is correct, it gets fixed. "Correct but not worth fixing" is not a valid dismissal reason.
