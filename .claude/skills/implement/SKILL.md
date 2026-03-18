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

---

## Purpose

Codify the full workflow for dispatching and coordinating an epic when the user requests implementation. The main session (user-facing agent) is the spawner and router: it reads the epic, spawns implementers, code-reviewer, and PM, assigns stories with full context blocks, routes completion reports to PM (AC verification, status updates) and code-reviewer (quality review), manages merge-back, cascades to newly unblocked stories, and runs the closure sequence. The main session does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git merge`, `git mv`, `git add`, `git commit`) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

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

Read the epic's `## Dispatch Team` section.

- **If present and non-empty**: Extract the listed agent types. These are the implementers to spawn. PM and code-reviewer are always spawned as infrastructure -- they are not listed in the Dispatch Team section.
- **If absent or empty**: Use the Agent Selection routing table in `/.claude/rules/agent-routing.md` to determine which agent types are needed based on story domains and "Files to Create or Modify" sections. Read story files to make this determination.

### Multi-Wave Planning

Review the full dependency graph across all stories:

- **Single-wave epics** (no inter-story dependencies): All implementers are spawned at once in Phase 2.
- **Multi-wave epics** (stories have dependencies on other stories): Identify which agent types are needed for wave 1 (stories with no unsatisfied dependencies) and which are needed for later waves. Spawn wave-1 agents in Phase 2. Spawn later-wave agents directly as their dependencies complete during Phase 3.

---

## Phase 2: Dispatch

Create the team and spawn all agents. The main session spawns implementers, code-reviewer, and PM.

### Step 1: Create the team

Use `TeamCreate` to create a dispatch team for the epic.

### Step 2: Spawn implementing agents, code-reviewer, and PM

Spawn each implementing agent with `isolation: "worktree"` (unless the context-layer exception applies -- see Phase 3 Step 2). This gives each agent an isolated copy of the repository via `git worktree`, preventing concurrent stories from interfering with each other's working trees.

Implementer spawn context:

```
You are a [agent-type] agent on the [team-name] team. Wait for the main session to assign you a story via SendMessage. Do not begin work until you receive your story assignment with the full story file text and Technical Notes.
```

If this is a multi-wave epic, spawn only wave-1 agents now. Later-wave agents are spawned during Phase 3 as dependencies complete (each with `isolation: "worktree"` by default).

**Spawn the code-reviewer** alongside the implementing agents. The code-reviewer is infrastructure, not a story-specific implementer -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. The code-reviewer is NOT spawned with `isolation: "worktree"` -- it needs to access any implementer's worktree path to read their changed files and run `git diff`. Code-reviewer spawn context:

```
You are the code-reviewer agent on the [team-name] team. Wait for review assignments from the main session via SendMessage. Do not self-initiate reviews. Each review assignment will include a story ID, the full story file text, epic Technical Notes, and the implementer's Files Changed list. When the implementer worked in a worktree, the assignment will include the worktree path -- use it when reading files and running git diff.
```

**Spawn the product-manager (PM)** alongside implementers and code-reviewer. PM is infrastructure -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. PM is NOT spawned with `isolation: "worktree"` -- it reads/writes status files in the main checkout and needs direct access. PM spawn context:

```
You are the product-manager agent on the [team-name] team. Your role during dispatch is status management and AC verification. You own: story status file updates (TODO -> IN_PROGRESS -> DONE), epic Stories table updates, epic status transitions (READY -> ACTIVE -> COMPLETED), and AC verification ("did they build what was specified"). Wait for routing from the main session via SendMessage -- the main session will send you status update requests and completion reports for AC verification. Do not self-initiate work. Epic file: [absolute path to epic.md].
```

**PM context window recovery**: If PM's context fills during large epics, the main session respawns PM with a fresh summary of current epic state: which stories are DONE, which are IN_PROGRESS, the current wave, and a reminder of PM's role. No state is lost because PM's work products (status files, epic table) persist on disk.

### Step 3: Set epic to ACTIVE

If this is the first dispatch of this epic (status is `READY`), route to PM to update the epic status to `ACTIVE`.

---

## Phase 3: Coordination

The main session routes work during dispatch. PM owns statuses and AC verification. This is the core dispatch loop.

### Step 1: Identify eligible stories

Find stories with `Status: TODO` whose blocking dependencies are all `DONE`.

### Step 2: Route stories to agents

For each eligible story:

1. **Check Agent Hint.** If the story has an `## Agent Hint` field, prefer that agent type.
2. **Check context-layer routing.** Scan the story's "Files to Create or Modify" section. If **any** file matches a context-layer path (see Routing Precedence in `/.claude/rules/agent-routing.md`), that story MUST go to `claude-architect` regardless of the Agent Hint. **Isolation depends on file mix:** if the story modifies ONLY context-layer files, spawn WITHOUT `isolation: "worktree"` (runs in the main checkout because these files are shared infrastructure that must be immediately visible to all agents). If the story is mixed (context-layer + code files), spawn `claude-architect` WITH `isolation: "worktree"` -- the architect edits both context-layer and code files from the worktree.
3. **Fall back to routing table.** If no Agent Hint and no context-layer match, use the Agent Selection table in `/.claude/rules/agent-routing.md` to determine the agent type from file paths and story domain.

### Step 3: Update statuses

Route to PM to mark each eligible story `IN_PROGRESS` in both the story file and the epic Stories table.

### Step 4: Assign stories to implementers

Send each implementer their story via `SendMessage` with a full context block:

```
You are executing story E-NNN-SS: [Story Title]

Story file: /absolute/path/to/E-NNN-SS.md

[Full contents of the story file]

Context from parent epic Technical Notes:

[Full Technical Notes section from epic.md]

Completed dependencies:
- E-NNN-01: [title] -- DONE

Handoff context from completed dependencies:
- From E-NNN-01: [artifact path and description declared in upstream story's Handoff Context section]

You are working in a git worktree (an isolated copy of the repository). Your working directory will be something like `/tmp/.worktrees/baseball-crawl-abc123/` instead of `/workspaces/baseball-crawl`.

## Worktree Constraints -- What You MUST NOT Do

### No Docker Interaction
- Do NOT run `docker compose` commands (up, down, restart, ps, logs, build)
- Do NOT run `curl localhost:8001` or any health checks against the app
- Do NOT attempt to rebuild or restart the app container
- The Docker stack reads from the main checkout, not from your worktree

### No App/Credential/Database CLI Commands
- Do NOT run `bb data sync`, `bb data crawl`, `bb data load`
- Do NOT run `bb creds check`, `bb creds refresh`, `bb creds import`
- Do NOT run `bb db reset`, `bb db backup`
- Do NOT run `bb status`
- These commands assume the main checkout and interact with the live app, credentials, or database

### No Proxy Commands
- Do NOT run `bb proxy *` commands (`bb proxy report`, `bb proxy endpoints`, `bb proxy check`, etc.)
- Do NOT run `./scripts/proxy-*.sh` scripts
- These assume main-checkout paths for `proxy/data/`

### No Credential or Data File Access
- `.env` is gitignored and **does not exist** in your worktree
- `data/` is gitignored and **does not exist** in your worktree
- Do NOT attempt to read credentials, access the app database, or reference data files
- If your code needs `.env` values, use `__file__`-relative path resolution (not cwd-relative)

### No Context-Layer Modifications (Unless Assigned)
- Do NOT modify `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, or `.claude/agent-memory/**`
- Context-layer files are shared infrastructure and must be modified in the main checkout
- Exception: if your story is explicitly a context-layer story assigned to you in the main checkout (pure context-layer stories are never dispatched to worktrees)
- Exception: mixed stories (context-layer + code files) are dispatched to `claude-architect` WITH worktree isolation. In this case, the architect edits both context-layer and code files from the worktree, and changes are merged back like any other worktree story.

### No Branch or Worktree Management
- Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d`
- Do NOT attempt to merge your work back into the main branch
- Branch management, merging, and worktree cleanup are handled by the main session

## What You CAN Do

### Run Tests
- `pytest` is safe to run from worktrees
- Tests use `tmp_path`, `:memory:` SQLite databases, and mocked HTTP -- they do not depend on `.env`, `data/`, or Docker

### Read and Write Source Code
- Edit files in `src/`, `tests/`, `migrations/`, `scripts/`, `docs/`, and other tracked directories
- Your changes are on an isolated branch and will be merged by the main session after review

### Use Git for Inspection
- `git status`, `git diff`, `git log` are safe
- Committing your changes is fine -- the main session handles the merge

## File Paths in Reports
- When reporting `## Files Changed`, use **absolute paths** (e.g., `/tmp/.worktrees/baseball-crawl-abc123/src/foo.py`). The main session and code-reviewer need these paths to locate your work in the worktree.

Satisfy all acceptance criteria and report back when complete. Do not modify story status files, check AC boxes, or update the epic Stories table. Report completion to the main session; PM will verify ACs and update statuses independently.

IMPORTANT: When reporting completion, include a `## Files Changed` section listing ALL files you created, modified, or deleted, with absolute paths and status annotations. Use your worktree-absolute paths (e.g., `/tmp/.worktrees/baseball-crawl-abc123/src/foo.py`). Include files across all directories (src/, tests/, scripts/, migrations/, docs/, etc.) -- not just source files.

Also include a `## Test Results` section reporting: the pytest command you ran, the pass/fail count, and any failure details. Example: `pytest tests/test_foo.py -- 12 passed, 0 failed`. If you ran no tests, state why.

Example:

## Files Changed
- /tmp/.worktrees/baseball-crawl-abc123/src/crawlers/roster.py (modified)
- /tmp/.worktrees/baseball-crawl-abc123/tests/test_roster.py (new)
- /tmp/.worktrees/baseball-crawl-abc123/src/crawlers/old_module.py (deleted)
- /tmp/.worktrees/baseball-crawl-abc123/src/crawlers/new_name.py (renamed from /tmp/.worktrees/baseball-crawl-abc123/src/crawlers/old_name.py)
```

**Context-layer stories** (spawned without worktree isolation): Omit the worktree paragraph from the context block. Use main-checkout paths in the Files Changed example instead.

**Context block requirements**:
- Include the **full story file text** verbatim. Never summarize.
- Include the **full epic Technical Notes** verbatim.
- When a story has completed upstream dependencies with Handoff Context declarations, include the declared artifact paths and descriptions.

Assign stories in parallel when they have no file conflicts. Before routing stories to parallel agents, compare their "Files to Create or Modify" sections -- overlapping stories are serialized (assigned sequentially, not concurrently).

**Migration serialization**: Migration stories (files under `migrations/`) must never run concurrently, even without explicit file overlap. Concurrent migrations cause numbering conflicts (two migrations may claim the same sequence number). Serialize all stories whose "Files to Create or Modify" include paths under `migrations/`.

### Step 5: Monitor, review, and verify

> **Boundary reminder:** If you are about to read source files, run `git log`, `grep`, or inspect the implementation to "quickly check" something -- stop. That is domain work regardless of size, and it must be routed to the appropriate agent. Route it through the review/verification sequence below (see Domain Work During Dispatch in `dispatch-pattern.md`).

Stay active in the team. As each implementer reports completion (with `## Files Changed`):

1. **Check context-layer-only skip condition.** If the story modifies ONLY context-layer files (`.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/`, `CLAUDE.md`) and no Python code, route to PM for AC verification and status update. The code-reviewer is skipped for context-layer-only stories -- PM verifies ACs alone. After PM confirms ACs pass, proceed to Step 6 (PM marks DONE). If PM rejects ACs, route feedback to the implementer for revision.

2. **Route code stories to the code-reviewer AND PM.** For stories that touch Python code or any non-context-layer files, send the work to both the code-reviewer (quality review) and PM (AC verification) in parallel. Send the code-reviewer the work using this template:

```
Review story E-NNN-SS: [Title]

Story file: /absolute/path/to/E-NNN-SS.md
[Full story file text]

Epic Technical Notes:
[Full Technical Notes]

Implementer worktree path: [worktree path, e.g. /tmp/.worktrees/baseball-crawl-abc123/]
(Use this path to read changed files and run `git diff`. Run `cd <worktree-path> && git diff main..HEAD` to see changes. Do NOT run pytest from the worktree -- verify ACs through file inspection. See `.claude/agents/code-reviewer.md` Worktree Review section.)

Implementer-reported files changed:
[Files Changed section from implementer's completion message -- paths will be worktree-absolute]

Implementer-reported test results:
[Test Results section from implementer's completion message -- pytest command, pass/fail count, failures]

Review round: 1 of 2 (circuit breaker)

Review this story's implementation against all acceptance criteria and the review rubric. The implementer's Files Changed list is the primary scope. Cross-reference it against the story's "Files to Create or Modify" section to flag any missing or unexpected files (divergence is a SHOULD FIX finding -- implementers may legitimately touch unlisted files, but it should be called out). Note: `git diff --name-only` is repo-wide and may include changes from parallel stories or untracked files -- use it as advisory context, not as the authoritative scope for this story. Report findings using the structured format.
```

When the implementer did NOT work in a worktree (context-layer stories that touch non-context files, or stories spawned without isolation for other reasons), omit the "Implementer worktree path" paragraph.

3. **Triage ALL findings.** Before any merge or routing decision, the main session reads every finding (MUST FIX and SHOULD FIX) and triages each SHOULD FIX item into one of two tracks:
   - **Accept track (fix it)**: The finding improves code touched by the story. Route to the implementer immediately alongside MUST FIX items. No user confirmation needed.
   - **Dismiss track (close it)**: The finding targets pre-existing code not modified by the story, or the main session disagrees with the recommendation. For each finding on the dismiss track, the main session presents the finding and its dismissal reasoning to the user in plain English, then waits for user confirmation before closing. If the user vetoes a dismissal, the finding moves to the accept track and is routed to the implementer.
   - **When uncertain, bias toward accepting** -- prefer fixing over dismissing.

   Every finding reaches a terminal state during the story: FIXED or DISMISSED. No deferral path exists.

4. **If the reviewer returns APPROVED and PM verifies ACs pass** (no MUST FIX findings, ACs satisfied): Triage any SHOULD FIX findings per step 3 above. If all SHOULD FIX items are dismissed (or there are none), run the merge-back sequence (see Step 5a below), then route to PM to mark the story `DONE`. If any SHOULD FIX items are accepted, route them to the implementer who wrote the code before merge-back. After the implementer fixes them, send the updated work back to the reviewer for re-review. The main session routes findings to implementers for resolution -- it NEVER creates, modifies, or deletes any file itself.

   **If PM rejects ACs** (regardless of reviewer verdict): Route PM's AC feedback to the implementer alongside any code-review MUST FIX items and accepted SHOULD FIX items. After the implementer revises, both PM and the code-reviewer re-evaluate. See Gate Interaction below.

   **PM-Reviewer AC Disagreement**: If the code-reviewer flags an AC as MUST FIX but PM verifies that AC as PASS, the main session removes the AC-based finding from the MUST FIX list before routing to the implementer. If removing AC-based items empties the MUST FIX list, the story passes the review gate (effectively APPROVED for merge-back). Non-AC MUST FIX findings (bugs, security, conventions) are the reviewer's exclusive domain and are unaffected by PM override. The full PM-Reviewer AC Disagreement resolution matrix: (1) Reviewer APPROVED + PM pass = merge-back. (2) Reviewer NOT APPROVED, non-AC MUST FIX only = route to implementer. (3) Reviewer NOT APPROVED, ALL MUST FIX are AC-related, PM says pass = PM override, proceed to merge-back. (4) Mixed AC + non-AC MUST FIX, PM says pass = remove AC items, route only non-AC items. (5) PM says fail = route PM feedback to implementer regardless. Non-AC findings (bugs, security, conventions) are the reviewer's exclusive domain -- PM cannot override those.

5. **If the reviewer returns NOT APPROVED** (MUST FIX findings): Triage SHOULD FIX findings per step 3 above. Route MUST FIX items plus any accepted SHOULD FIX items to the implementer who wrote the code with the review round number (e.g., "Round 1 of 2 -- items to fix below"). The main session NEVER creates, modifies, or deletes any file itself -- all fixes are routed to the implementer. The implementer fixes the issues in the same worktree and reports completion again (with updated `## Files Changed`). Send the updated work back to the reviewer for Round 2 using an expanded template that includes the prior findings:

```
Review story E-NNN-SS: [Title] (Round 2)

Story file: /absolute/path/to/E-NNN-SS.md
[Full story file text]

Epic Technical Notes:
[Full Technical Notes]

Implementer worktree path: [worktree path]
(Same instructions as round 1 -- read files and run git diff from this path.)

Implementer-reported files changed:
[Updated Files Changed section from implementer's round-2 completion message]

Implementer-reported test results:
[Test Results section from implementer's round-2 completion message]

Round 1 findings routed to implementer:
[Paste the MUST FIX findings and accepted SHOULD FIX findings from round 1 verbatim]

Review round: 2 of 2 (circuit breaker)

This is a round-2 re-review. The implementer was asked to fix the Round 1 findings listed above (MUST FIX items plus any SHOULD FIX items accepted by the main session during triage). Perform a full re-review of all changed files, but focus on whether the Round 1 MUST FIX items are resolved and whether the fixes introduced any new issues. Report findings using the structured format.
```

6. **Circuit breaker.** Max 2 review rounds per story. If the 2nd review still has MUST FIX findings, escalate to the user with the findings summary and present options:
   - (a) Fix it themselves
   - (b) Tell the implementer to try again (resets the circuit breaker)
   - (c) Override the reviewer and proceed to merge-back + PM closure (explicit user override -- the user assumes responsibility for unresolved findings)
   - (d) Abandon the story
   The main session does NOT mark the story DONE and does NOT loop further without user direction.

### Gate Interaction

When PM rejects ACs, route PM's feedback to the implementer alongside any code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. PM AC rejection does NOT have its own circuit breaker -- the code-reviewer's 2-round circuit breaker governs the overall loop. If the circuit breaker fires, escalate to the user regardless of PM AC status.

### Step 5a: Merge-back (worktree stories only)

After both the code-reviewer approves and PM verifies ACs pass for a story implemented in a worktree (or PM alone approves for context-layer-only stories), the main session runs the merge-back sequence from the main checkout BEFORE marking DONE or cascading. A story is NOT marked DONE until its branch is successfully merged.

**Merge-back sequence:**

1. `git merge --no-ff <worktree-branch>` from the main checkout -- creates a merge commit preserving story history.
2. **If merge succeeds:**
   - Remove the worktree: `git worktree remove <path>` (retry with `--force` if it fails due to untracked files).
   - Delete the branch: `git branch -d <branch>` (safe because the branch is fully merged).
   - Route to PM to mark the story `DONE` (Step 6).
   - Proceed to cascade (Step 6).
3. **If merge conflicts:**
   - The story remains `IN_PROGRESS`.
   - Cascade is blocked for dependent stories only (non-dependent stories can proceed).
   - The worktree stays active for inspection.
   - Escalate to the user with conflict details: which files conflict and between which stories.
   - The user resolves the conflict in the main checkout (not the worktree).
   - After resolution, the main session removes the worktree, deletes the branch, routes to PM to mark DONE, and proceeds to cascade.

For stories that were NOT implemented in a worktree (context-layer stories), skip this step -- proceed directly to PM marking DONE.

### Step 6: Cascade

After PM marks a story DONE, check for newly unblocked stories (stories whose blocking dependencies are now all DONE).

- If the required agent type is already on the team, assign the story directly (repeat from Step 2).
- If a new agent type is needed, spawn the agent and assign the story.
- If no more stories are eligible and some are still in progress, wait for more completions.
- If all stories are DONE, proceed to Phase 4 (or Phase 5 if no review chain).

---

## Phase 4: Optional Review Chain

If the user specified the "and review" modifier (e.g., "implement E-NNN and review"):

- After all stories are verified DONE, chain into the code review workflow at `.claude/skills/codex-review/SKILL.md` (headless path).
- The main session invokes the review skill directly.
- If the review produces findings, they flow through the codex-review skill's remediation loop (Steps 5-7): the original implementer on the dispatch team validates each finding and remediates confirmed issues, PM records dispositions in the epic's History section, and remediation fixes are not re-reviewed.
- After the remediation loop completes (or if the review produces no findings), proceed to Phase 5 (closure).

If the modifier was not specified, skip this phase and proceed directly to Phase 5.

---

## Phase 5: Closure Sequence

When all stories are verified DONE (and the optional review chain is complete), execute the following closure sequence in order.

**Before spinning down the team:**

### Step 1: Validate all work

Confirm all stories are DONE. Per-story AC verification was performed by PM during Phase 3 (for all stories), and code quality was verified by the code-reviewer (for code stories). This step confirms completion status -- it is not a re-review of all code.

**Worktree verification:** Verify all worktree branches have been merged into the current branch. Run `git branch` to confirm no worktree branches remain unmerged. Then run `git worktree list --porcelain` as a safety-net sweep for orphaned worktrees from error paths. If any orphans are found, force-remove them (`git worktree remove --force <path>`, then `git branch -D <branch>` for unmerged branches). Run `git worktree prune` as a final cleanup for stale registrations. Per-story worktree cleanup happens at merge-back time (Phase 3 Step 5a) -- this closure check catches only orphans from error paths.

### Step 2: Update the epic completely

Route to PM, who performs:

- Confirm all story file statuses are DONE.
- Epic Stories table reflects current reality (all rows DONE).
- Epic status updated to COMPLETED.
- History entry added with the completion date and a summary of what was accomplished.
- Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information (credentials, tokens, secrets) OUT of epic files.

### Step 3: Documentation assessment

Review the epic's scope against the update triggers in `.claude/rules/documentation.md`. If any trigger fires, spawn docs-writer (if not already on the team) to update affected docs before archiving. If no trigger fires, record "No documentation impact" in the epic's History section. The epic MUST NOT be archived until this assessment is complete and any required doc updates are done.

### Step 3a: Context-layer assessment

Evaluate the epic's impact on the context layer per `.claude/rules/context-layer-assessment.md`. Assess each of the six triggers with an explicit yes/no verdict and record all verdicts in the epic's History section. If any trigger fires, spawn claude-architect (if not already on the team) to codify the findings before archiving. The epic MUST NOT be archived until this assessment is complete and any required codification is done.

### Step 4: Archive the epic

Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/` and verify the move is fully staged before proceeding.

**Move method:** Use `git mv epics/E-NNN-slug/ .project/archive/E-NNN-slug/` (not plain `mv`). `git mv` atomically stages both the new files at the destination and the deletions at the source.

**Verification gate:** After the move, run `git status --porcelain` and grep the output for the epic slug. Any line referencing `epics/E-NNN-slug/` or `.project/archive/E-NNN-slug/` that has a non-space character in column 2 (the working-tree status column) represents an unstaged change -- status codes like ` D`, `??`, `RM`, `AM`, `MM`, etc. Stage all such changes with `git add` before proceeding. The main session MUST NOT proceed past this step with unstaged archive-related changes in the working tree.

The main session performs the `git mv` and verification directly (this is a git operation, same category as merge-back). Do not proceed to team shutdown until the archive is confirmed and fully staged.

### Step 5: Update PM memory

Route to PM to move the epic from "Active Epics" to "Archived Epics" in the PM's MEMORY.md (`.claude/agent-memory/product-manager/MEMORY.md`). PM notes any follow-up work or newly unblocked items.

### Step 6: Review ideas backlog

PM checks `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

### Step 7: Review vision signals

PM checks whether `docs/vision-signals.md` has any content after the `## Signals` heading. If unprocessed signals exist, PM mentions them in the closure summary and the main session asks the user if they want to "curate the vision." This is advisory, not blocking -- the closure sequence proceeds regardless of the user's answer.

### Step 8: Present a summary to the user

Before ending the dispatch, present a clear summary including:
- Epic ID and title
- List of stories completed (with brief descriptions)
- Key artifacts created or modified
- Any follow-up work identified
- Any ideas that may now be promotable

### Step 9: Shut down all teammates

Send a `shutdown_request` to each agent on the team (implementers, code-reviewer, and PM). Wait for shutdown confirmations. Delete the team.

**After spinning down the team:**

### Step 10: Offer to scan and commit

After shutting down teammates and deleting the team, offer to run the PII scan and commit the changes. Commit must NOT happen automatically -- the user must explicitly approve before any commit happens.

---

## Workflow Summary

```
User says "implement E-NNN" (optionally "and review")
  |
  v
Main session loads this skill
  |
  v
Prerequisites: verify epic exists, status is READY or ACTIVE
  |
  v
[If DRAFT/COMPLETED/ABANDONED/BLOCKED: refuse and stop]
  |
  v
Phase 0: tmux rename-window "E-NNN dispatch" (silent, non-blocking)
  |
  v
Phase 1: Read epic's Dispatch Team section
  - Extract implementer types
  - Plan multi-wave spawning if dependencies exist
  |
  v
Phase 2: Create team, spawn implementers (worktree) + code-reviewer (no worktree) + PM (no worktree)
  - Context-layer stories: spawned WITHOUT worktree isolation
  - Code-reviewer + PM spawned automatically (infrastructure, not in Dispatch Team)
  - PM owns status management + AC verification
  - Route to PM: set epic to ACTIVE if currently READY
  |
  v
Phase 3: Coordination loop
  - Identify eligible stories (TODO + deps satisfied)
  - Route to agent type (Agent Hint > context-layer check > routing table)
  - Context-layer stories -> claude-architect, no worktree
  - Route to PM: mark stories IN_PROGRESS
  - Assign with full context blocks (+ worktree notice + status prohibition)
  - Implementer reports completion with ## Files Changed (worktree-absolute paths)
      |
      v
    Context-layer-only? --YES--> Route to PM for AC verification + status update
      |
      NO
      |
      v
    Send to code-reviewer (round 1 of 2) AND PM (AC verification) in parallel
      |
      v
    Both gates must pass:
      - Code-reviewer: quality review -> APPROVED / NOT APPROVED
      - PM: AC verification -> pass / fail
      - PM-Reviewer AC disagreement: PM override for AC-related MUST FIX items
      |
      v
    Main session triages ALL findings:
      - MUST FIX: always routed to implementer (main session NEVER creates, modifies, or deletes any file itself)
      - SHOULD FIX accept track: route to implementer immediately (no user wait)
      - SHOULD FIX dismiss track: present reasoning to user, wait for confirmation
        - User confirms -> finding DISMISSED
        - User vetoes -> moves to accept track, routed to implementer
      - No deferral path -- every finding ends FIXED or DISMISSED
      |
      v
    Items to fix? --NO--> Merge-back: git merge --no-ff -> remove worktree -> delete branch
      |                     -> Route to PM: mark DONE
      YES                   [If merge conflict: escalate to user, block dependent cascade only]
      |
      v
    Route findings to implementer who wrote the code, implementer fixes in same worktree
      |
      v
    Send to code-reviewer (round 2 of 2) + PM re-verifies ACs
      |
      v
    Items to fix? --NO--> Merge-back -> Route to PM: mark DONE
      |
      YES
      |
      v
    Escalate to user (circuit breaker)
  - Cascade to newly unblocked stories (merge MUST complete before cascade)
  - Spawn later-wave agents as dependencies complete (with isolation: "worktree")
  |
  v
[If "and review": Phase 4 -- chain into codex-review skill (headless)]
  |
  v
Phase 5: Closure sequence
  - Validate all work (confirm DONE + PM verified ACs + all branches merged)
  - Sweep for orphaned worktrees (git worktree list --porcelain; force-remove; prune)
  - Route to PM: update epic to COMPLETED with history entry
  - Documentation assessment (spawn docs-writer if needed)
  - Context-layer assessment (spawn claude-architect if needed)
  - Archive epic to /.project/archive/ (git mv + verify fully staged)
  - PM: update PM memory
  - PM: review ideas backlog
  - PM: review vision signals (advisory)
  - Present summary to user
  - Shut down team (implementers + code-reviewer + PM)
  - Offer to scan and commit
```

---

## Edge Cases

### Epic Not Found
If no directory matching `E-NNN` exists under `/epics/`, report to the user and stop. Do not search the archive (`/.project/archive/`) -- archived epics are completed or abandoned.

### Epic Is DRAFT
Refuse with explanation: "Epic E-NNN is in DRAFT status. It must be marked READY after refinement is complete before dispatch." Do not offer to mark it READY -- that requires verifying stories have testable acceptance criteria and expert consultation is done.

### Epic Is COMPLETED or ABANDONED
Refuse: "Epic E-NNN is already [COMPLETED/ABANDONED] and cannot be dispatched."

### No TODO Stories With Satisfied Dependencies
If all remaining stories are BLOCKED (waiting on incomplete dependencies) or all stories are already DONE, report the situation to the user. If stories are blocked, explain what they are waiting on.

### Implementer Spawn Fails
Follow the Dispatch Failure Protocol in `/.claude/rules/workflow-discipline.md`: report the failure to the user with the specific reason and ask how to proceed. Do not improvise a workaround.

### "And Review" With No Uncommitted Changes
If the review chain runs but there are no uncommitted changes to review, the codex-review skill handles this gracefully. No special handling needed here.

### Code-Reviewer Context Window Fills
If the code-reviewer's context window fills during a large epic (8+ stories), the main session may shut down and respawn the reviewer. No state is lost because each review assignment is self-contained -- the reviewer reads the story file and changed files fresh for every assignment.

### PM Context Window Fills
If PM's context fills during a large epic, the main session respawns PM with a fresh summary of current epic state: which stories are DONE, which are IN_PROGRESS, the current wave, and a reminder of PM's role (status management + AC verification). No state is lost because PM's work products (status files, epic table) persist on disk.

---

## Anti-Patterns

1. **Do not fall for the "quick check" trap.** The main session's most common boundary violation starts with a rationalization: "too small to route," "I'll just verify this one thing," "quick check." Quick checks are domain work regardless of size. The main session MUST NOT: create, modify, or delete any file (its only direct file operations are git commands and writes to its own memory directory); verify ACs or update statuses (PM's exclusive responsibility); bypass the code-reviewer by verifying code quality directly; absorb a crashed agent's work instead of respawning the agent; apply fixes -- not even trivial one-line fixes. When something feels too small to route, route it anyway.
2. **Do not summarize context blocks.** Always send the full story file text and full Technical Notes verbatim. Summarizing loses acceptance criteria, file paths, and constraints that implementers need.
3. **Do not proceed to closure with unverified stories.** If any AC is unmet, send the implementer back. Do not close the epic with partial completion.
4. **Do not skip the documentation assessment.** The epic cannot be archived until the documentation impact is evaluated per `.claude/rules/documentation.md`.
5. **Do not commit automatically.** The closure sequence offers to commit -- the user must explicitly approve.
6. **Do not skip PM spawning.** PM handles all status updates and AC verification during dispatch. PM is spawned alongside implementers and code-reviewer as infrastructure for every dispatch.
7. **Do not skip the context-layer assessment.** The epic cannot be archived until the context-layer impact is evaluated per `.claude/rules/context-layer-assessment.md`.
8. **Do not defer SHOULD FIX findings to epic History.** Every finding must reach a terminal state (FIXED or DISMISSED) during the story. The main session triages each SHOULD FIX item: accept it (route to implementer immediately) or dismiss it (present reasoning to user and wait for confirmation). There is no deferral path.
9. **Do not spawn context-layer stories with worktree isolation.** Context-layer files (CLAUDE.md, `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, etc.) are shared infrastructure. Stories modifying only these files must run in the main checkout without `isolation: "worktree"`.
