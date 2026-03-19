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

Codify the full workflow for dispatching and coordinating an epic when the user requests implementation. The main session (user-facing agent) is the spawner and router: it reads the epic, creates an epic-level worktree as the accumulation point for all story patches, spawns implementers, code-reviewer, and PM, assigns stories with full context blocks, routes completion reports to PM (AC verification, status updates) and code-reviewer (quality review), manages patch-apply merge-back to the epic worktree, cascades to newly unblocked stories, and runs the closure sequence (merge epic worktree to main, commit, cleanup). The main session does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git worktree add/remove` for epic and story worktree lifecycle, `git apply` for merge-back to the epic worktree, `git diff`/`git apply` for closure merge to main, `git add -A` and `git commit` for the closure commit, `git branch -D` for branch cleanup, `git mv` for archival) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

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

Create the epic worktree, the team, and spawn all agents. The main session creates the epic worktree first, then spawns implementers, code-reviewer, and PM.

### Step 1: Create the epic worktree

Before team creation, create an epic-level worktree that serves as the accumulation point for all story patches during dispatch. Story patches are applied here (not to the main checkout), isolating the epic's changes from the main working tree.

**Command** (substitute the actual epic ID):

```bash
git worktree add -b epic/E-NNN /tmp/.worktrees/baseball-crawl-E-NNN
```

- **Path**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (e.g., `/tmp/.worktrees/baseball-crawl-E-137/`)
- **Branch**: `epic/E-NNN` (e.g., `epic/E-137`)
- Store the epic worktree path for use throughout dispatch -- it is passed to PM and code-reviewer in their spawn context and used in every merge-back operation.

If the branch or worktree already exists (e.g., resuming a previously interrupted dispatch), reuse the existing worktree rather than failing.

### Step 2: Create the team

Use `TeamCreate` to create a dispatch team for the epic.

### Step 3: Spawn implementing agents, code-reviewer, and PM

Spawn each implementing agent with `isolation: "worktree"` (unless the context-layer exception applies -- see Phase 3 Step 2). This gives each agent an isolated copy of the repository via `git worktree` (a story-level worktree, separate from the epic worktree), preventing concurrent stories from interfering with each other's working trees.

Implementer spawn context:

```
You are a [agent-type] agent on the [team-name] team. Wait for the main session to assign you a story via SendMessage. Do not begin work until you receive your story assignment with the full story file text and Technical Notes.
```

If this is a multi-wave epic, spawn only wave-1 agents now. Later-wave agents are spawned during Phase 3 as dependencies complete (each with `isolation: "worktree"` by default).

**Spawn the code-reviewer** alongside the implementing agents. The code-reviewer is infrastructure, not a story-specific implementer -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. The code-reviewer is NOT spawned with `isolation: "worktree"` -- it needs to access any implementer's worktree path to read their changed files and run `git diff`. Code-reviewer spawn context:

```
You are the code-reviewer agent on the [team-name] team. Wait for review assignments from the main session via SendMessage. Do not self-initiate reviews. Each review assignment will include a story ID, the full story file text, epic Technical Notes, and the implementer's Files Changed list. When the implementer worked in a worktree, the assignment will include the worktree path -- use it when reading files and running git diff. Epic worktree path: [epic-worktree-path] (e.g., /tmp/.worktrees/baseball-crawl-E-NNN/) -- this is where all story patches accumulate during dispatch; use it for integration-level diffs when needed.
```

**Spawn the product-manager (PM)** alongside implementers and code-reviewer. PM is infrastructure -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. PM is NOT spawned with `isolation: "worktree"` -- it reads/writes status files in the main checkout and needs direct access. PM spawn context:

```
You are the product-manager agent on the [team-name] team. Your role during dispatch is status management and AC verification. You own: story status file updates (TODO -> IN_PROGRESS -> DONE), epic Stories table updates, epic status transitions (READY -> ACTIVE -> COMPLETED), and AC verification ("did they build what was specified"). Wait for routing from the main session via SendMessage -- the main session will send you status update requests and completion reports for AC verification. Do not self-initiate work. Epic file: [absolute path to epic.md]. Epic worktree path: [epic-worktree-path] (e.g., /tmp/.worktrees/baseball-crawl-E-NNN/) -- this is where all story patches accumulate during dispatch; reference it when verifying ACs (accumulated changes live here, not in the main checkout; exception: context-layer-only stories run in the main checkout without worktree isolation -- their changes remain in the main checkout, not the epic worktree).
```

**PM context window recovery**: If PM's context fills during large epics, the main session respawns PM with a fresh summary of current epic state: which stories are DONE, which are IN_PROGRESS, the current wave, and a reminder of PM's role. No state is lost because PM's work products (status files, epic table) persist on disk.

### Step 4: Set epic to ACTIVE

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

   **Context-layer exception in the epic worktree model:** Context-layer-only stories run in the main checkout, so their changes are NOT accumulated in the epic worktree and are NOT included in the epic's atomic commit. Their changes remain **uncommitted** in the main checkout throughout dispatch. This is intentional: committing context-layer changes to main mid-dispatch would shift the diff base (the `main` HEAD that all story patches and the epic closure merge are generated against) and break the epic-scoped diff guarantee. Context-layer changes are committed separately AFTER the epic's atomic commit succeeds (see Phase 5 Step 8, item 8). Mixed stories (context-layer + code) run in a worktree, and their patches merge to the epic worktree like any other story.
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
- Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d/-D`
- Do NOT attempt to merge your work back into the main branch
- Branch management, merging, and worktree cleanup are handled by the main session

## What You CAN Do

### Run Tests
- `pytest` is safe to run from worktrees
- Tests use `tmp_path`, `:memory:` SQLite databases, and mocked HTTP -- they do not depend on `.env`, `data/`, or Docker

### Read and Write Source Code
- Edit files in `src/`, `tests/`, `migrations/`, `scripts/`, `docs/`, and other tracked directories
- Your changes stay in the working tree -- there are no commits and no branch divergence. After review, the main session extracts your staged changes via patch-apply.

### Use Git for Inspection
- `git status`, `git diff`, `git log` are safe
- Before reporting completion, run `git add -A` to stage all changes (new files, modifications, deletions). Do NOT run `git commit` -- the main session collects your staged changes via patch-apply after review

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
(Use this path to read changed files and run `git diff`. Run `cd <worktree-path> && git diff --cached main` to see all staged changes. Do NOT run pytest from the worktree -- verify ACs through file inspection. See `.claude/agents/code-reviewer.md` Worktree Review section.)

Implementer-reported files changed:
[Files Changed section from implementer's completion message -- paths will be worktree-absolute]

Implementer-reported test results:
[Test Results section from implementer's completion message -- pytest command, pass/fail count, failures]

Review round: 1 of 2 (circuit breaker)

Review this story's implementation against all acceptance criteria and the review rubric. The implementer's Files Changed list is the primary scope. Cross-reference it against the story's "Files to Create or Modify" section to flag any missing or unexpected files (divergence is a SHOULD FIX finding -- implementers may legitimately touch unlisted files, but it should be called out). Note: `git diff --name-only` is repo-wide and may include changes from parallel stories or untracked files -- use it as advisory context, not as the authoritative scope for this story. Report findings using the structured format.
```

When the implementer did NOT work in a worktree (context-layer stories that touch non-context files, or stories spawned without isolation for other reasons), omit the "Implementer worktree path" paragraph.

3. **Triage ALL findings.** Before any merge or routing decision, the main session classifies every finding (MUST FIX and SHOULD FIX) as **valid** or **invalid**:
   - **Valid finding** (correct analysis of the code): Route to the implementer for fixing, regardless of severity (MUST FIX or SHOULD FIX), size, or cosmetic nature. "Correct but too small to fix" is NOT a valid dismissal reason.
   - **Invalid finding** (false positive, misunderstanding of the code, or targets code not modified by the story): Dismiss with explanation. No user confirmation needed.

   The distinction between MUST FIX and SHOULD FIX is preserved in the code-reviewer's output (it signals severity), but the handling for all valid findings is the same: fix it. Every finding reaches a terminal state during the story: FIXED or DISMISSED. No deferral path exists.

4. **If the reviewer returns APPROVED and PM verifies ACs pass** (no MUST FIX findings, ACs satisfied): Triage any SHOULD FIX findings per step 3 above. If all findings are invalid (dismissed) or there are none, run the merge-back sequence (see Step 5a below), then route to PM to mark the story `DONE`. If any valid findings exist, route them to the implementer who wrote the code before merge-back. After the implementer fixes them, send the updated work back to the reviewer for re-review. The main session routes findings to implementers for resolution -- it NEVER creates, modifies, or deletes any file itself.

   **If PM rejects ACs** (regardless of reviewer verdict): Route PM's AC feedback to the implementer alongside any valid code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. See Gate Interaction below.

   **PM-Reviewer AC Disagreement**: If the code-reviewer flags an AC as MUST FIX but PM verifies that AC as PASS, the main session removes the AC-based finding from the valid findings list before routing to the implementer. If removing AC-based items empties the valid findings list, the story passes the review gate (effectively APPROVED for merge-back). Non-AC MUST FIX findings (bugs, security, conventions) are the reviewer's exclusive domain and are unaffected by PM override. The full PM-Reviewer AC Disagreement resolution matrix: (1) Reviewer APPROVED + PM pass = merge-back. (2) Reviewer NOT APPROVED, non-AC MUST FIX only = route to implementer. (3) Reviewer NOT APPROVED, ALL MUST FIX are AC-related, PM says pass = PM override, proceed to merge-back. (4) Mixed AC + non-AC MUST FIX, PM says pass = remove AC items, route only non-AC items. (5) PM says fail = route PM feedback to implementer regardless. Non-AC findings (bugs, security, conventions) are the reviewer's exclusive domain -- PM cannot override those.

5. **If the reviewer returns NOT APPROVED** (MUST FIX findings): Triage all findings per step 3 above. Route all valid findings (MUST FIX and any valid SHOULD FIX items) to the implementer who wrote the code with the review round number (e.g., "Round 1 of 2 -- items to fix below"). The main session NEVER creates, modifies, or deletes any file itself -- all fixes are routed to the implementer. The implementer fixes the issues in the same worktree and reports completion again (with updated `## Files Changed`). Send the updated work back to the reviewer for Round 2 using an expanded template that includes the prior findings:

```
Review story E-NNN-SS: [Title] (Round 2)

Story file: /absolute/path/to/E-NNN-SS.md
[Full story file text]

Epic Technical Notes:
[Full Technical Notes]

Implementer worktree path: [worktree path]
(Same instructions as round 1 -- read files and run `git diff --cached main` from this path.)

Implementer-reported files changed:
[Updated Files Changed section from implementer's round-2 completion message]

Implementer-reported test results:
[Test Results section from implementer's round-2 completion message]

Round 1 findings routed to implementer:
[Paste all valid findings (MUST FIX and valid SHOULD FIX) from round 1 verbatim]

Review round: 2 of 2 (circuit breaker)

This is a round-2 re-review. The implementer was asked to fix the Round 1 findings listed above (all valid findings -- MUST FIX and valid SHOULD FIX items). Perform a full re-review of all changed files, but focus on whether the Round 1 findings are resolved and whether the fixes introduced any new issues. Report findings using the structured format.
```

6. **Circuit breaker.** Max 2 review rounds per story. If the 2nd review still has MUST FIX findings, escalate to the user with the findings summary and present options:
   - (a) Fix it themselves
   - (b) Tell the implementer to try again (resets the circuit breaker)
   - (c) Override the reviewer and proceed to merge-back + PM closure (explicit user override -- the user assumes responsibility for unresolved findings)
   - (d) Abandon the story
   The main session does NOT mark the story DONE and does NOT loop further without user direction.

### Gate Interaction

When PM rejects ACs, route PM's feedback to the implementer alongside any code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. PM AC rejection does NOT have its own circuit breaker -- the code-reviewer's 2-round circuit breaker governs the overall loop. If the circuit breaker fires, escalate to the user regardless of PM AC status.

### Step 5a: Merge-back via patch-apply (worktree stories only)

After both the code-reviewer approves and PM verifies ACs pass for a story implemented in a worktree (or PM alone approves for context-layer-only stories), the main session runs the patch-apply merge-back sequence to apply the story's changes to the **epic worktree** BEFORE marking DONE or cascading. A story is NOT marked DONE until its changes are successfully applied.

**Patch-apply sequence:**

1. **In the story worktree**: Generate a patch from staged changes: `cd <story-worktree-path> && git diff --binary --cached main > /tmp/E-NNN-SS.patch`
2. **In the epic worktree**: Apply the patch: `cd <epic-worktree-path> && git apply --3way /tmp/E-NNN-SS.patch` (the `--3way` flag falls back to 3-way merge semantics when sequential same-file patches have context-line mismatches; compatible with `--binary`).
3. **Stage in epic worktree**: After successful apply, stage the changes: `cd <epic-worktree-path> && git add -A`. This keeps the epic worktree's index up to date as story patches accumulate.
4. **If apply succeeds:**
   - Remove the story worktree: `git worktree remove <story-worktree-path>` (retry with `--force` if it fails due to untracked files).
   - Delete the story branch: `git branch -D <story-branch>` (force delete because the branch has no commits beyond main).
   - Route to PM to mark the story `DONE` (Step 6).
   - Proceed to cascade (Step 6).
5. **If apply fails (conflict):**
   - The story remains `IN_PROGRESS`.
   - Cascade is blocked for dependent stories only (non-dependent stories can proceed).
   - The story worktree stays active for inspection.
   - Escalate to the user with conflict details.
   - Recovery in epic worktree: `cd <epic-worktree-path> && git reset --hard HEAD && git clean -fd` to reset (handles unmerged index entries from `--3way` conflicts), then retry after conflict resolution.
   - After resolution, the main session removes the story worktree, deletes the story branch (`-D`), routes to PM to mark DONE, and proceeds to cascade.

For stories that were NOT implemented in a worktree (context-layer stories), skip this step -- their changes are already in the main checkout. Proceed directly to PM marking DONE.

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

**Worktree verification:** Run `git worktree list --porcelain` to verify no **story** worktrees remain (all should have been removed during per-story patch-apply merge-back in Phase 3 Step 5a). The **epic worktree** (`/tmp/.worktrees/baseball-crawl-E-NNN/`) MUST still be present at this point -- it is cleaned up later in Step 10 after the closure merge to main succeeds. If any orphaned story worktrees are found, force-remove them (`git worktree remove --force <path>`, then `git branch -D <branch>`). Run `git worktree prune` as a final cleanup for stale registrations. This closure check catches only orphans from error paths -- per-story worktree cleanup happens at merge-back time.

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

### Step 4: Review ideas backlog

PM checks `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

### Step 5: Review vision signals

PM checks whether `docs/vision-signals.md` has any content after the `## Signals` heading. If unprocessed signals exist, PM mentions them in the closure summary and the main session asks the user if they want to "curate the vision." This is advisory, not blocking -- the closure sequence proceeds regardless of the user's answer.

### Step 6: Present a summary to the user

Before ending the dispatch, present a clear summary including:
- Epic ID and title
- List of stories completed (with brief descriptions)
- Key artifacts created or modified
- Any follow-up work identified
- Any ideas that may now be promotable

### Step 7: Shut down implementers and code-reviewer

Send a `shutdown_request` to each implementer and to the code-reviewer. Wait for shutdown confirmations. **Do NOT shut down PM yet** -- PM is needed for memory updates after archive.

**After spinning down implementers and code-reviewer:**

### Step 8: Closure merge and commit

Merge the epic worktree's accumulated changes into the main checkout and produce a single commit.

**Migration merge-time scan:** Before generating the epic patch, check whether the epic worktree's staged changes include any new migration files (paths under `migrations/`). If they do, check whether main has added new migrations since the epic worktree branched (compare `ls migrations/` in both the epic worktree and the main checkout). If main has new migrations that did not exist when the epic worktree was created, flag the potential numbering conflict to the user before proceeding. The user decides whether to continue, renumber, or abort.

**Closure merge sequence:**

1. **Stage in epic worktree**: `cd <epic-worktree-path> && git add -A` (ensure all accumulated story patches are staged).
2. **Generate epic patch**: `cd <epic-worktree-path> && git diff --binary --cached main > /tmp/E-NNN-epic.patch`
3. **Dry-run in main checkout**: `cd /workspaces/baseball-crawl && git apply --check --3way /tmp/E-NNN-epic.patch`
4. **If dry-run succeeds**: Apply for real: `cd /workspaces/baseball-crawl && git apply --3way /tmp/E-NNN-epic.patch`
5. **PII scan**: Run on applied changes (the pre-commit hook covers this automatically).
6. **Stage and present**: Stage the applied epic changes. If context-layer-only stories left uncommitted changes in the main checkout, use targeted staging (`git add` on the specific files from the epic patch -- list them via `git apply --stat /tmp/E-NNN-epic.patch` or stage all then unstage context-layer paths) to avoid accidentally including context-layer changes in the epic commit. Present the staged changes summary to the user and ask for explicit approval before committing.
7. **Commit**: `git commit` with a conventional commit message: `feat(E-NNN): <epic title>`.
8. **Context-layer commit**: After the epic commit succeeds, check for uncommitted context-layer changes in the main checkout (from context-layer-only stories that ran without worktree isolation). Run `git status --porcelain` and look for changes to context-layer paths (`.claude/`, `CLAUDE.md`). If found, stage them (`git add .claude/ CLAUDE.md` or the specific changed paths) and commit in a separate commit: `chore(E-NNN): context-layer updates`. If the epic commit failed or was aborted (steps 3-7), do NOT commit context-layer changes -- they remain uncommitted in the main checkout for the user to handle manually.
9. **Cleanup**: `git worktree remove <epic-worktree-path> && git branch -D epic/E-NNN`.

**If dry-run fails (conflict with main):** Present a conflict report to the user with the affected files. Options:
- (a) Resolve manually (user fixes conflicts, then the main session retries from step 3)
- (b) Abort (epic worktree is preserved for manual recovery; the main session does not clean it up)

The user must explicitly approve before the commit happens. If PII scan catches issues, nothing is committed -- the atomic approach makes this safer than partial commits. Commit must NOT happen automatically.

### Step 9: Archive the epic

Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/` and verify the move is fully staged before proceeding.

**Move method:** Use `git mv epics/E-NNN-slug/ .project/archive/E-NNN-slug/` (not plain `mv`). `git mv` atomically stages both the new files at the destination and the deletions at the source.

**Verification gate:** After the move, run `git status --porcelain` and grep the output for the epic slug. Any line referencing `epics/E-NNN-slug/` or `.project/archive/E-NNN-slug/` that has a non-space character in column 2 (the working-tree status column) represents an unstaged change -- status codes like ` D`, `??`, `RM`, `AM`, `MM`, etc. Stage all such changes with `git add` before proceeding. The main session MUST NOT proceed past this step with unstaged archive-related changes in the working tree.

The main session performs the `git mv` and verification directly (this is a git operation, same category as merge-back).

### Step 10: Update PM memory

Route to PM to move the epic from "Active Epics" to "Archived Epics" in the PM's MEMORY.md (`.claude/agent-memory/product-manager/MEMORY.md`). PM notes any follow-up work or newly unblocked items. PM is still running (shut down was deferred in Step 7).

### Step 11: Archive commit

Commit the archive move and PM memory update: `git add -A && git commit -m "chore(E-NNN): archive epic"`.

### Step 12: Shut down PM and delete team

Send a `shutdown_request` to PM. Wait for shutdown confirmation. Delete the team.

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
Phase 2: Create epic worktree, team, spawn agents
  - Create epic worktree: git worktree add -b epic/E-NNN /tmp/.worktrees/baseball-crawl-E-NNN
  - Create dispatch team
  - Spawn implementers (story worktree) + code-reviewer (no worktree) + PM (no worktree)
  - Pass epic worktree path to PM and code-reviewer in spawn context
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
  - Implementer stages all changes (`git add -A`) and reports completion with ## Files Changed
      |
      v
    Context-layer-only? --YES--> Route to PM for AC verification + status update
      |                           (changes stay UNCOMMITTED in main checkout -- NOT in epic worktree)
      NO                          (committed separately AFTER epic commit in Phase 5 Step 8)
      |
      v
    Send to code-reviewer (round 1 of 2) AND PM (AC verification) in parallel
      - Code-reviewer runs `git diff --cached main` to review staged changes
      |
      v
    Both gates must pass:
      - Code-reviewer: quality review -> APPROVED / NOT APPROVED
      - PM: AC verification -> pass / fail
      - PM-Reviewer AC disagreement: PM override for AC-related MUST FIX items
      |
      v
    Main session classifies ALL findings:
      - Valid finding (correct analysis): route to implementer for fixing
      - Invalid finding (false positive, misunderstanding, untouched code): dismiss with explanation
      - No "correct but too small to fix" -- valid findings always get fixed
      - No deferral path -- every finding ends FIXED or DISMISSED
      |
      v
    Items to fix? --NO--> Patch-apply: generate patch in story worktree -> apply in EPIC worktree
      |                     -> stage in epic worktree -> remove story worktree -> delete branch (-D)
      YES                   -> Route to PM: mark DONE
      |                     [If apply fails: escalate to user, block dependent cascade only]
      v
    Route findings to implementer who wrote the code, implementer fixes in same worktree
      |
      v
    Send to code-reviewer (round 2 of 2) + PM re-verifies ACs
      |
      v
    Items to fix? --NO--> Patch-apply to epic worktree -> Route to PM: mark DONE
      |
      YES
      |
      v
    Escalate to user (circuit breaker)
  - Cascade to newly unblocked stories (patch-apply MUST complete before cascade)
  - Spawn later-wave agents as dependencies complete (with isolation: "worktree")
  |
  v
[If "and review": Phase 4 -- chain into codex-review skill (headless)]
  |
  v
Phase 5: Closure sequence
  - Validate all work (confirm DONE + PM verified ACs + no story worktrees remain)
  - Sweep for orphaned STORY worktrees (epic worktree must still be present)
  - Route to PM: update epic to COMPLETED with history entry
  - Documentation assessment (spawn docs-writer if needed)
  - Context-layer assessment (spawn claude-architect if needed)
  - PM: review ideas backlog
  - PM: review vision signals (advisory)
  - Present summary to user
  - Shut down implementers + code-reviewer (PM stays alive)
  - Closure merge: migration scan -> epic patch -> dry-run -> apply in main -> PII scan
    -> user approval -> commit feat(E-NNN) -> context-layer commit (if any)
    -> cleanup epic worktree + branch
    [If dry-run fails: present conflict report, user decides resolve or abort]
  - Archive epic to /.project/archive/ (git mv + verify fully staged)
  - PM updates its own memory
  - Archive commit (git add -A && git commit)
  - Shut down PM, delete team
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
8. **Do not defer findings to epic History.** Every finding must reach a terminal state (FIXED or DISMISSED) during the story. Valid findings are routed to the implementer; invalid findings are dismissed with explanation. There is no deferral path.
9. **Do not spawn context-layer stories with worktree isolation.** Context-layer files (CLAUDE.md, `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, etc.) are shared infrastructure. Stories modifying only these files must run in the main checkout without `isolation: "worktree"`.
10. **Do not commit in worktrees.** Implementers stage changes (`git add -A`) but NEVER commit. The main session extracts staged changes via patch-apply (`git diff --binary --cached main`) and produces a single atomic commit at closure. Committing in a worktree breaks the patch-apply merge-back flow.
11. **Do not use `git merge` for merge-back.** Merge-back uses the patch-apply sequence: generate a patch from staged changes in the story worktree, apply it in the epic worktree. `git merge --no-ff` is not used because there are no commits to merge.
12. **Do not apply story patches to the main checkout.** Story patches are applied to the epic worktree (`/tmp/.worktrees/baseball-crawl-E-NNN/`), not to `/workspaces/baseball-crawl`. The main checkout only receives changes via the closure merge sequence in Phase 5 Step 8.
13. **Do not dismiss valid findings based on size or cosmetic nature.** If the code-reviewer's finding is a correct analysis of the code, it gets fixed -- regardless of whether it is a MUST FIX or SHOULD FIX, regardless of how small or cosmetic it appears. "Correct but not worth fixing" is not a valid dismissal reason. Only false positives, misunderstandings, and findings about untouched code are dismissed.
