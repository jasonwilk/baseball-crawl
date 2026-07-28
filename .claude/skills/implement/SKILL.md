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

**Chaining modifier**: The user may append "and review" or "and codex review" to any trigger phrase (e.g., "implement E-NNN and review", "start E-NNN and codex review"). This adds the optional Codex review pass (Phase 4) after implementation completes. Note: the code-reviewer's Closure CR Integration Review (Phase 5 Step 1c) is **unconditional** and runs on every dispatch regardless of this modifier -- the modifier only gates the Codex pass. See Phase 4 and Phase 5 Step 1c.

**Plan skill handoff**: This skill may also be loaded by the plan skill's Phase 5 when the user used a compound trigger ("plan and dispatch"). In this case, `handoff_from_plan = true` and a planning team is already active. The implement skill reuses the existing team rather than creating a fresh one. See Phase 1 and Phase 2 for handoff-specific paths.

---

## Purpose

Codify the full workflow for dispatching and coordinating an epic when the user requests implementation. The main session (user-facing agent) is the spawner and router: it reads the epic, creates an epic worktree, spawns implementers, code-reviewer, and PM (all working in the epic worktree), assigns stories serially, routes completion reports through review and AC verification, manages the staging boundary between stories, and runs the closure sequence (merge epic worktree to main, commit, cleanup). The main session does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git worktree add/remove` for epic worktree lifecycle, `git diff`/`git apply` for closure merge to main, `git add -A` for staging boundary and closure commit, `git commit` for the closure commit, `git branch -D` for branch cleanup, `git mv` for archival) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

**Subagent model**: The agents this skill spawns are long-lived, resumable named subagents (spawned via the `Agent` tool, with the team forming implicitly on the first spawn); the runtime flag they depend on is stated once in `CLAUDE.md` (Agent Ecosystem) and is not repeated in the spawn blocks below.

**Enforcement model**: A PreToolUse hook (`.claude/hooks/worktree-guard.sh`) blocks Write and Edit operations to the main checkout during dispatch (all paths, with no agent-memory exception -- own-memory writes go to the worktree copy). Outside dispatch, it blocks implementation paths only (`src/`, `tests/`, `migrations/`, `scripts/`). This provides deterministic enforcement that dispatch work happens in worktrees. The hook is the primary mechanism; instruction-based constraints in this skill are backup for edge cases the hook cannot cover (e.g., Bash file writes).

When invoked via plan skill handoff (`handoff_from_plan = true`), the planning team is already active with PM and domain experts. The implement skill reuses these agents rather than creating a fresh team, preserving expert context from the planning session (unified team lifecycle).

This skill is the authoritative source for dispatch procedures. Agent routing tables are in `/.claude/rules/agent-routing.md`. See `/.claude/rules/dispatch-pattern.md` for a brief overview of dispatch roles.

---

## Prerequisites

Before dispatch, verify:

1. **The target epic exists.** Check that `/epics/E-NNN-slug/epic.md` exists. If not found, search `/epics/` for a directory starting with `E-NNN`. If no match, report to the user: "Epic E-NNN not found in `/epics/`." and stop.

2. **The epic status is `READY` or `ACTIVE`.** Read the epic file and check the `## Status` section.
   - If `READY`: apply the **READY Freshness Gate** (`.claude/rules/workflow-discipline.md`) before proceeding. If the epic has been READY for more than 60 days (see the gate for how age is measured -- READY date if recorded, else last commit touching `epics/E-NNN-slug/`), it is **STALE**: do NOT dispatch. Report to the user that the epic is stale and route to PM to either re-confirm it against `docs/ROADMAP.md` (resetting the READY date) or demote it to `DRAFT`. Dispatch proceeds only after re-confirmation. Otherwise (READY ≤ 60 days): proceed.
   - If `ACTIVE`: proceed (mid-dispatch; the freshness gate does not apply).
   - If `DRAFT`: refuse. Tell the user: "Epic E-NNN is in DRAFT status. It must be marked READY after refinement is complete before it can be dispatched."
   - If `COMPLETED`: refuse. Tell the user: "Epic E-NNN is already COMPLETED."
   - If `ABANDONED`: refuse. Tell the user: "Epic E-NNN has been ABANDONED."
   - If `BLOCKED`: report the blocked status and any blocking details to the user. Do not proceed.

3. **The epic's plan is committed.** Run `cd /workspaces/baseball-crawl && git status --porcelain -- epics/E-NNN-slug/`. If the output is non-empty, the plan has uncommitted changes and dispatching would create the epic worktree from a HEAD that lacks the plan files. Refuse dispatch with a message that:
   - Lists each uncommitted file path from the `git status --porcelain` output, verbatim.
   - Provides a concrete remediation command for the user to run before retrying, of the form:
     ```
     cd /workspaces/baseball-crawl && git add epics/E-NNN-slug/ && git commit -m "feat(E-NNN): plan <title> (READY)"
     ```

   This check does NOT auto-commit. User approval for the planning commit is preserved at plan skill Step 2a (`.claude/skills/plan/SKILL.md`), which is the sole owner of the planning commit path. Prerequisites refuses rather than auto-committing. The plan skill is not modified by this check -- the Prerequisites clause is a backstop, not a replacement.

   **Handoff exception:** Skip this check when the implement skill was loaded via plan skill Phase 5 Step 3c handoff (the compound-trigger "plan and dispatch" path). On that path, plan skill Step 2a already owns the commit invariant -- the planning team committed (or skipped under Step 2a's documented skip behavior) before handing off, so the worktree HEAD already reflects the planning state. The check runs on the standalone "implement E-NNN" invocation path. The skip is determined by the trigger pattern that loaded this skill, not by an abstract flag -- it activates only when the load originated from a compound "plan and dispatch" trigger handed off via plan skill Phase 5 Step 3c.

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

**If `handoff_from_plan = true`** (plan skill handoff): The planning team is already active, the epic worktree was created by the plan skill's handoff sequence, and agents have been transitioned. Skip Steps 1-3 (epic worktree creation, team formation, agent spawning). Proceed directly to Step 4 (set epic to ACTIVE). Code-reviewer is already on the team -- either spawned during the plan skill's Phase 3 (internal review cycle) and transitioned to code-review mode, or spawned fresh during Phase 5 Step 3a if Phase 3 was skipped. Do not re-spawn it. If any additional implementer types are needed that were not on the planning team, spawn them now using the universal spawn context below.

**If `handoff_from_plan = false`** (standard dispatch): Create the epic worktree and spawn all agents as described below (the team forms implicitly on the first spawn).

### Step 1: Create the epic worktree

Before spawning agents, create an epic-level worktree where all agents work during dispatch.

**Command** (substitute the actual epic ID):

```bash
git worktree add -b epic/E-NNN /tmp/.worktrees/baseball-crawl-E-NNN
```

- **Path**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (e.g., `/tmp/.worktrees/baseball-crawl-E-137/`)
- **Branch**: `epic/E-NNN` (e.g., `epic/E-137`)
- Store the epic worktree path for use throughout dispatch -- all agents receive it in their spawn context.

If the branch or worktree already exists (e.g., resuming a previously interrupted dispatch), reuse the existing worktree rather than failing.

### Step 2: Team formation (implicit)

There is no explicit team-creation step -- the team forms implicitly when the first subagent is spawned in Step 3.

### Step 3: Spawn implementing agents, code-reviewer, and PM

All agents are spawned WITHOUT `isolation: "worktree"` and receive the epic worktree path in their spawn context. They use absolute paths under the epic worktree for all file operations.

**Universal implementer spawn context:**

```
You are a [agent-type] subagent. Wait for the main session to assign you a story via SendMessage. Do not begin work until you receive your story assignment with the full story file text and Technical Notes.

Your working directory for all file operations: [epic-worktree-path]
(e.g., /tmp/.worktrees/baseball-crawl-E-NNN/)

Use absolute paths under this directory for ALL file reads, writes, and git commands.
Do NOT use Write/Edit on paths starting with `/workspaces/baseball-crawl/` -- that is the main checkout, not your worktree.

Deliver every result via SendMessage to "main". Your plain-text output is not
visible to anyone; only the tool call delivers. Report when the story is done or
when you are blocked -- do not go idle holding a finished answer.

Any brief I send you is a RELAY of the story file and the epic. Verify it
against those files before acting, and where they disagree, THE FILE WINS and my
brief is wrong. Tell me when you find a conflict.
```

Those last two paragraphs are not boilerplate to trim: **8 of 10 spawns in one audited session finished and went idle without delivering**, and E-276's planning shipped 9 relay defects, every one caught (when it was caught at all) by a receiver checking the brief against the artifact. See `.claude/rules/dispatch-pattern.md`, "Briefs, Channels, and Context".

**Spawn the code-reviewer** alongside the implementing agents. The code-reviewer is infrastructure, not a story-specific implementer -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. Code-reviewer spawn context:

```
You are the code-reviewer subagent. Wait for review assignments from the main session via SendMessage. Do not self-initiate reviews. Each review assignment will include a story ID, the full story file text, epic Technical Notes, and the implementer's Files Changed list.

Epic worktree path: [epic-worktree-path]
All story work happens in this worktree. Use it when reading files and running git diff.
Review the current story's changes via `cd [epic-worktree-path] && git diff` (unstaged changes = current story).
Review all accumulated changes via `cd [epic-worktree-path] && git diff --cached $(git merge-base epic/E-NNN main)` (staged = prior stories).
The base is the merge base, NEVER bare `main`: `main` moves while the epic runs, and in this worktree `HEAD` is `epic/E-NNN`, so a bare-`main` diff mixes main's own post-branch commits into what reads as the epic's changes.
Do NOT use Write/Edit on paths starting with `/workspaces/baseball-crawl/` -- that is the main checkout, not your worktree.
```

**Spawn the product-manager (PM)** alongside implementers and code-reviewer. PM is infrastructure -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch. PM spawn context:

```
You are the product-manager subagent. Your role during dispatch is status management and AC verification. You own: story status file updates (TODO -> IN_PROGRESS -> DONE), epic Stories table updates, epic status transitions (READY -> ACTIVE -> COMPLETED), and AC verification ("did they build what was specified"). Wait for routing from the main session via SendMessage -- the main session will send you status update requests and completion reports for AC verification. Do not self-initiate work.

Epic file: [absolute path to epic.md in epic worktree]
Epic worktree path: [epic-worktree-path]
All story work happens in this worktree. Use absolute paths under the epic worktree for all file operations (story files, epic files, status updates).
Do NOT use Write/Edit on paths starting with `/workspaces/baseball-crawl/` -- that is the main checkout, not your worktree. This includes your own memory: write `.claude/agent-memory/product-manager/` in the WORKTREE copy (the dispatch-active hook denies main-checkout Write/Edit with no agent-memory exception), so your closure memory updates ride the closure patch.
```

**PM context window recovery**: The normal path is `SendMessage` resumption -- PM is a long-lived resumable subagent, so the main session re-engages it with its context intact. As a documented fallback, if PM's context fills during large epics, the main session respawns PM with a fresh summary of current epic state: which stories are DONE, which are IN_PROGRESS, and a reminder of PM's role. No state is lost because PM's work products (status files, epic table) persist on disk.

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

**Enforcement**: A PreToolUse hook blocks Write/Edit to the main checkout during dispatch. You are in the epic worktree, so your writes pass. Do NOT use main-checkout paths.

**Prohibited:**
- Do NOT use Write/Edit on paths starting with `/workspaces/baseball-crawl/` -- that is the main checkout, not your worktree
- Bash file writes (`echo >`, `sed -i`, `cat >`, `cp`, `mv`) to `src/`, `tests/`, `migrations/`, `scripts/` -- use Write/Edit tools instead (hook-covered, reviewable diffs)
- `docker compose`, `curl localhost:8001`, app health checks (Docker reads from main, not worktree)
- `bb data *`, `bb creds *`, `bb db *`, `bb status`, `bb proxy *`, `./scripts/proxy-*.sh` (assume main checkout)
- Reading `.env` or `data/` (gitignored, do not exist in worktree)
- `git commit`, `git merge`, `git rebase`, `git worktree remove`, `git branch -d/-D`
- `cd /workspaces/baseball-crawl` -- stay in the epic worktree

**Pytest limitation**: a pytest run from the worktree exercises the *worktree's* own uncommitted `src/` (not the merged tree the epic closes against) -- `tests/__init__.py` puts the repo root on `sys.path[0]`, ahead of the editable-install finder. Run tests for verification, but understand a green worktree run is not evidence about the merged closure tree. Report results in your completion message.

**Permitted**: `git status/diff/log` from worktree. `git diff` = your unstaged changes (this story). `git diff --cached $(git merge-base epic/E-NNN main)` = prior stories' staged changes -- use the merge base, never bare `main`, which would fold main's own post-branch commits into the view. Edit files via Write/Edit tools with absolute worktree paths.

**Expert recommendations are provisional until you trace scope.** When a story, spec, Technical Notes section, or relayed expert consultation names a specific file, function, signature, or schema change, treat that recommendation as a starting point -- not the final answer. Before committing the change, grep `src/`, `scripts/`, `tests/`, and `templates/` for all construction sites, callers, and consumers of the named entity, and verify the recommendation still holds across the actual surface area. Schema and structural recommendations made from a quick read often miss sites the expert did not see; the implementer is the one who finds them.

**Completion**: Report with `## Files Changed` (absolute worktree paths, e.g., `[epic-worktree-path]/src/foo.py (modified)`), `## Test Results` (command, pass/fail, failures), and `## Behavioral Changes`. The Behavioral Changes section is ALWAYS present. List any function whose signature, return type, raised exceptions, or documented side effects changed. Internal refactors that preserve the function's contract are NOT behavioral changes. Format: `- \`function_name()\` in \`file.py\`: [what changed]`. Write "None" when no behavioral changes occurred -- this makes it explicit that you considered the question. This section supplements (does not replace) the code-reviewer's own caller audit -- CR still independently scans the diff for non-obvious behavioral changes. Do NOT run `git add -A` (main session manages staging). Do not modify story status files or epic tables.
```

**Context block requirements**: Include the full story file text and full Technical Notes verbatim. Include Handoff Context from completed upstream dependencies.

### Step 5: Monitor, review, and verify

> **Boundary reminder:** If you are about to read source files, run `git log`, `grep`, or inspect the implementation to "quickly check" something -- stop. That is domain work regardless of size, and it must be routed to the appropriate agent. Route it through the review/verification sequence below (see Domain Work During Dispatch in `dispatch-pattern.md`).

When the implementer reports completion (with `## Files Changed`):

**Post-story path verification**: Check every file path in the implementer's `## Files Changed` section. Every path MUST start with the epic worktree pattern (`/tmp/.worktrees/baseball-crawl-E-NNN/`). If any path starts with `/workspaces/baseball-crawl/` (main checkout) or any other unexpected prefix, STOP and escalate to the user before proceeding. This catches agents that accidentally worked in the wrong directory.

**AC×surface enumeration**: When verifying a *conditional* AC -- one that applies "only when X" / "for Y" / a vocabulary mapping -- PM (and the code-reviewer, for code stories) applies the same per-surface enumeration: verify the AC holds at every render/call/error path, not just the first happy path. This is the AC-verification-side companion to the AC×surface matrix in `.claude/agents/code-reviewer.md` (Priority 1).

1. **Check context-layer-only skip condition.** If the story modifies ONLY context-layer files (`.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/`, `CLAUDE.md`) and no Python code, route to PM for AC verification and status update. The code-reviewer is skipped for context-layer-only stories -- PM verifies ACs alone. After PM confirms ACs pass, proceed to the staging boundary (Step 5a). If PM rejects ACs, route feedback to the implementer for revision.

2. **Route code stories to the code-reviewer AND PM.** For stories that touch Python code or any non-context-layer files, send the work to both in parallel. Code-reviewer template:

```
Review story E-NNN-SS: [Title]
Story file: [epic-worktree-path]/epics/E-NNN-slug/E-NNN-SS.md
[Full story file text]
Epic Technical Notes: [Full Technical Notes]
Epic worktree path: [epic-worktree-path]
Review via `cd [epic-worktree-path] && git diff` (unstaged = this story). Do NOT run pytest for this per-story worktree review -- verify through file inspection (a worktree pytest run exercises the worktree's own uncommitted `src/`, not the merged tree, so a green per-story run is not authoritative about the closure state). The one place you run `python -m pytest tests/` is the Phase 5 Step 1b closure gate, against the main checkout.
Implementer files changed: [Files Changed section]
Implementer test results: [Test Results section]
[If applicable] ## API Endpoints Touched
[List of docs/api/endpoints/*.md files -- include when Files Changed or Files to Create or Modify contains paths under src/gamechanger/crawlers/, src/gamechanger/loaders/, or src/gamechanger/client.py. Derive specific endpoint docs from the story description/Technical Approach. If specific endpoints cannot be determined, include all docs/api/endpoints/*.md files. Omit this section entirely when no API-touching files are involved. See TN-4a heuristics.]
[If applicable] ## Migration Files
[List of migrations/*.sql files -- include when Files Changed or Files to Create or Modify contains paths under src/api/, src/gamechanger/loaders/, src/db/, migrations/, or templates referencing database columns. Omit this section entirely when no database code is involved. See TN-4a heuristics.]
[If applicable] ## Behavioral Changes
[From implementer's completion report. List of functions whose signature, return type, or observable behavior changed. This supplements CR's own caller audit -- CR still independently scans the diff for non-obvious behavioral changes the implementer may not have recognized. Omit this section when the implementer declared "None."]
Review round: 1 of 2 (circuit breaker)
Review against all ACs and the review rubric. Cross-reference Files Changed against "Files to Create or Modify" to flag missing/unexpected files.
```

**Derivation heuristics for structured context fields** (TN-4a): The main session uses these rules to decide which optional context sections to include in the CR assignment. Check both the story's "Files to Create or Modify" and the implementer's Files Changed list:

- **API Endpoints Touched**: Include when any file is under `src/gamechanger/crawlers/`, `src/gamechanger/loaders/`, or `src/gamechanger/client.py` (modules that parse API responses or make HTTP calls). `src/gamechanger/types.py` and similar utility modules do NOT trigger this field. Derive specific endpoint docs from the story's Technical Approach or description (e.g., if the story mentions "public team endpoint," include `docs/api/endpoints/get-public-teams-public_id.md`). If specific endpoints cannot be determined, include all files matching `docs/api/endpoints/*.md`.
- **Migration Files**: Include when any file is under `src/api/`, `src/gamechanger/loaders/`, `src/db/`, `migrations/`, or templates referencing database columns.
- **Behavioral Changes**: Include when the implementer's completion report contains a `## Behavioral Changes` section with content other than "None." Omit when the implementer declared "None."

3. **Triage ALL findings.** Before any routing decision, the main session classifies every finding (MUST FIX and SHOULD FIX) as **valid** or **invalid**:
   - **Valid finding** (correct analysis of the code): Route to the implementer for fixing, regardless of severity (MUST FIX or SHOULD FIX), size, or cosmetic nature. "Correct but too small to fix" is NOT a valid dismissal reason.
   - **Invalid finding** (false positive, misunderstanding of the code, or targets code not modified by the story): Dismiss with explanation. No user confirmation needed.

   The distinction between MUST FIX and SHOULD FIX is preserved in the code-reviewer's output (it signals severity), but the handling for all valid findings is the same: fix it. Every finding reaches a terminal state during the story: FIXED or DISMISSED. No deferral path exists.

4. **If the reviewer returns APPROVED and PM verifies ACs pass** (no MUST FIX findings, ACs satisfied): Triage any SHOULD FIX findings per step 3 above. If all findings are invalid (dismissed) or there are none, proceed to the staging boundary (Step 5a), then route to PM to mark the story `DONE`. If any valid findings exist, route them to the implementer before the staging boundary. After the implementer fixes them, send the updated work back to the reviewer for re-review. The main session routes findings to implementers for resolution -- it NEVER creates, modifies, or deletes any file itself.

   **If PM rejects ACs** (regardless of reviewer verdict): Route PM's AC feedback to the implementer alongside any valid code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. See Gate Interaction below.

   **PM-Reviewer AC Disagreement**: PM can override AC-related MUST FIX items (remove them from the valid findings list). Non-AC findings (bugs, security, conventions) are the reviewer's exclusive domain -- PM cannot override. If removing AC items empties the list, the story passes. PM fail always routes feedback to implementer regardless of reviewer verdict.

5. **If the reviewer returns NOT APPROVED** (MUST FIX findings): Triage all findings per step 3 above. Route all valid findings to the implementer with "Round 1 of 2 -- items to fix below." The implementer fixes in the epic worktree and reports again. Send updated work to the reviewer for Round 2 using the same template as round 1, adding: updated Files Changed and Test Results (annotating which files are new or changed in the remediation vs. carried forward from Round 1, so CR can focus the remediation regression guard on the new/changed files), updated Behavioral Changes from the implementer's revised completion report, the same structured context sections (API Endpoints Touched, Migration Files) from Round 1, and "Review round: 2 of 2 (circuit breaker)" with instructions to focus on whether round 1 findings are resolved and whether fixes introduced new issues.

6. **Circuit breaker.** Max 2 review rounds per story. If the 2nd review still has MUST FIX findings, escalate to the user with the findings summary and present options:
   - (a) Fix it themselves
   - (b) Tell the implementer to try again (resets the circuit breaker)
   - (c) Override the reviewer and proceed to staging boundary + PM closure (explicit user override)
   - (d) Abandon the story
   The main session does NOT mark the story DONE and does NOT loop further without user direction.

### Gate Interaction

When PM rejects ACs, route PM's feedback to the implementer alongside any code-review findings. After the implementer revises, both PM and the code-reviewer re-evaluate. If the circuit breaker fires, escalate to the user regardless of PM AC status.

### Step 5a: Staging boundary

After both the code-reviewer approves and PM verifies ACs pass for a story (or PM alone approves for context-layer-only stories), the main session runs the staging boundary protocol:

1. **Stage the story's changes**: `cd <epic-worktree-path> && git add -A`
2. This story's changes are now staged. The next story starts with a clean unstaged diff.
3. Route to PM to mark the story `DONE`.

The staging boundary is the inter-story isolation mechanism. After staging:
- `git diff` (unstaged) shows only the next story's changes
- `git diff --cached $(git merge-base epic/E-NNN main)` shows the cumulative view (all completed stories). The merge base, not bare `main` -- see Step 8 sub-step 3 for why.

### Step 6: Cascade

After PM marks a story DONE, check for newly unblocked stories (stories whose blocking dependencies are now all DONE).

- If more stories are eligible, assign the next one (repeat from Step 1 -- serial execution).
- If a new agent type is needed, spawn the agent using the universal spawn context.
- If no more stories are eligible and some are still in progress, wait for completions.
- If all stories are DONE, proceed to Phase 4 (if "and review" modifier was specified) or Phase 5 (if not).

---

## Phase 4: Optional Codex Review

If the user specified the "and review" modifier (e.g., "implement E-NNN and review"), run a Codex review against the epic worktree diff as a systematic validation pass. If the modifier was not specified, skip this phase and proceed directly to Phase 5 -- the **Closure CR Integration Review** (Phase 5 Step 1c) is UNCONDITIONAL and runs on every dispatch path regardless.

**Codex-first ordering**: Codex runs HERE, before the Phase 5 Closure CR Integration Review, so that the code-reviewer adjudicates a real finding list (Codex's findings plus the post-remediation diff) in a single pass instead of approving the epic and then reversing itself when Codex later surfaces issues (the approve-then-reverse failure seen in E-239, E-251, E-253). On the default (no-"and review") path Codex is skipped and only the unconditional Closure CR Integration Review runs, so there is never a reversal -- the ordering fix only bites when both run.

This phase uses a degradation chain: headless codex first, prompt-generation fallback on failure.

#### Step 1: Attempt headless codex review

Run the codex-review script with the epic worktree path via Bash:

```
timeout 1200 ./scripts/codex-review.sh --workdir <epic-worktree-path> uncommitted
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
3. Remediate valid findings using the **Remediation Spawn Context** (defined at the start of Phase 5). Stage fixes with `git add -A`.
4. PM records dispositions in the epic's History section.
5. **Codex does NOT re-review its own remediation** -- the Phase 5 Closure CR Integration Review is the adjudicating pass over the post-remediation diff. After remediation, proceed to Phase 5.
6. **Circuit breaker (2 rounds)**: If round 2 still has unresolved findings, escalate to the user: (a) fix it themselves, (b) retry (resets breaker), (c) override and proceed to Phase 5, (d) abandon.

#### Step 4: Prompt-generation fallback (graceful degradation)

When headless codex times out or fails: generate a review prompt using the codex-review skill's prompt-generation path (`.claude/skills/codex-review/SKILL.md`, Steps 1-3) with the epic worktree diff. Present the pause message + prompt to the user. Wait for: "no findings" (clean, skip to Phase 5), pasted findings (enter Step 3 triage), or "skip" (advance to Phase 5 without findings).

After Codex review completes (clean, remediated, skipped, or user override), proceed to Phase 5.

---

## Phase 5: Closure Sequence

**Phase boundary**: Phase 4 handles the optional Codex review (gated on "and review"). Phase 5 handles closure mechanics (status updates, assessments, commit, archive) plus the closure-time verification passes: the conditional invariant audit (Step 1a), the unconditional **Closure CR Integration Review** (Step 1c -- the last pre-merge review), the unconditional full-suite-green gate (Step 1b, executed post-merge at Step 8 sub-step 5), and the conditional **closure runtime smoke** (Step 1d, executed post-merge at Step 8 sub-step 5b when the diff touches a runtime surface). These are whole-epic verification passes, not a re-review of individual stories.

When all stories are verified DONE (and the optional Codex review is complete), execute the following closure sequence in order.

**Phase 5 entry precondition -- check the artifact, not your memory.** If the "and review" modifier is active, confirm the Codex findings artifact EXISTS before starting the Step 1c Closure CR Integration Review: `scripts/codex-review.sh` tees its output to a deterministic `/tmp/codex-review-<epoch>.txt`, so check for one with an mtime inside this session. **If it is absent, Phase 4 did not run -- run it now, before Step 1c.** In E-276 the hub skipped Phase 4 entirely and sent the code-reviewer straight into Phase 5 **while able to quote the step it had omitted**; the operator caught it in four words, no gate did. That is the whole reason this precondition names a file: **a precondition someone can satisfy from memory is not a precondition.** The ordering is not cosmetic -- Codex-first exists so the reviewer adjudicates one combined finding list instead of approving the epic and then reversing itself (E-239, E-251, E-253).

### Remediation Spawn Context

Several closure passes remediate findings by spawning an implementer into the epic worktree: the Phase 4 Codex review, the Step 1a invariant audit, the Step 1c Closure CR Integration Review, the Step 1b full-suite green gate, and the Step 1d closure runtime smoke (post-preflight epic-FAILs only -- a Step 1d env-FAIL escalates to the user instead of remediating). They ALL use the single spawn context defined here -- defined once, at the start of Phase 5, so its definition does not live behind the now-conditional Phase 4. Every consumer references it by the name **"Remediation Spawn Context."**

Remediate valid findings **one at a time** (serial, not parallel). For each finding: spawn an implementer, wait for completion, stage with `git add -A`, then proceed to the next finding. Select agent type via the routing table. Spawn WITHOUT `isolation: "worktree"`.

```
You are a [agent-type] subagent spawned for post-review remediation.
Working directory: <epic-worktree-path> -- use absolute paths for ALL file operations.
Constraints: Do NOT use Write/Edit on paths starting with `/workspaces/baseball-crawl/`. No git commit (git add -A only), no docker/bb/proxy commands, no .env/data/ access, no git merge/rebase/worktree/branch commands, no Bash file writes (echo/sed/cat/cp/mv) to src/tests/migrations/scripts/ -- use Write/Edit tools.
Remediation authorized by post-review remediation exception in workflow-discipline.md.
Finding to remediate: [finding details]
Fix and report with ## Files Changed (absolute paths) and ## Test Results.
```

**Before spinning down the team:**

### Step 1: Validate all work

Confirm all stories are DONE. Per-story AC verification was performed by PM during Phase 3 (for all stories), and code quality was verified by the code-reviewer (for code stories). This step confirms completion status -- it is not a re-review.

### Step 1a: Invariant audit (conditional)

If the epic introduced a **cross-cutting invariant** -- a new NOT NULL column on a stat or core table, a new required FK dimension, a new pattern every helper or call site must honor -- spawn the code-reviewer for a single full-codebase invariant audit pass (see Invariant Audit Mode in `.claude/agents/code-reviewer.md`). Per-story CR cannot see helpers in files no story touched; this audit closes that gap. Triage findings using the same rules as Phase 3 Step 5 item 3, remediate valid findings via the **Remediation Spawn Context**, and stage with `git add -A`.

**Mechanical trigger checklist** -- every trigger is evaluable from a **permitted artifact** (the diff or the Technical Notes), so the main session, which is barred from reading source, can fire the audit without inspecting code. The audit FIRES when any of the following holds:

- a **NOT NULL or FK migration in the diff** -- a `migrations/*.sql` file in `git diff --cached $(git merge-base epic/E-NNN main)` (merge base, not bare `main`, or another epic's migration landing on main could fire this trigger) that adds a `NOT NULL` column or a `FOREIGN KEY` / `REFERENCES` clause; OR
- a **canonical-helper signature change declared in the epic/story Technical Notes** -- a Technical-Notes statement that a CLAUDE.md "canonical" seam function's signature changed (e.g. `ensure_team_row`, `ensure_player_row`, `resolve_db_path`, `ensure_season_row`); OR
- a **new required field on a core INSERT, as declared in the epic/story Technical Notes** -- a Technical-Notes statement that every INSERT path into a stat/core table must now supply a new mandatory field.

A core-INSERT field change that is ABSENT from the Technical Notes is itself a planning gap (the Technical Notes are the artifact the main session reads); surface it rather than silently skipping. For any case these triggers do not cleanly cover, the existing **"if unsure, ask the user"** fallback is the backstop. Skip this step for epics that fire none of the triggers and introduced no new invariant.

### Step 1c: Closure CR Integration Review (unconditional)

This is the **last pre-merge review** and runs on **every** dispatch path -- unlike the Phase 4 Codex review, it is NOT gated on "and review". It is a holistic code-reviewer pass over the full epic diff in the **epic worktree**, positioned AFTER the Step 1a invariant audit (so it sees all prior remediation -- Codex's from Phase 4 and the invariant audit's -- plus the final combined diff) and BEFORE the Step 8 closure merge. Per-story CR (Phase 3) reviews changes in isolation; this integration review catches cross-story interactions, naming inconsistencies, import conflicts, and architectural issues that only appear when stories are combined.

**Why unconditional, and why after Codex**: a plain "implement E-NNN" -- the documented default -- previously closed with NO combined-diff reviewer at all, because both the integration review and Codex were gated on "and review". Making this pass unconditional closes that gap. And because Codex (Phase 4) runs first, the code-reviewer adjudicates Codex's finding list plus the post-remediation diff in one pass, instead of approving the epic and then reversing itself when Codex surfaces issues (E-239 / E-251 / E-253).

**Context-layer epics**: context-layer-only stories skip per-story CR by design (Phase 3 Step 5 item 1), so this unconditional closure pass is where a context-layer epic gets its combined-diff review. The doc-sweep rule (`.claude/rules/doc-sweep.md`) auto-loads for the code-reviewer whenever the diff touches matching doc/context-layer files (via CR's Step-2 rule-glob mechanism), requiring a semantic read plus synonym expansion rather than a token-grep-only sweep.

**Surface-removal epics**: when the epic DELETES a route, surface, or widely-used symbol, this review MUST repo-wide grep each removed route/symbol across ALL tests (not just story-touched files) — removed surfaces commonly leave generic usages in untouched test files (e.g. a deleted route used as an authenticated-200 probe) that per-story review cannot see, and that otherwise surface only at the full-suite-green gate.

#### Generate the full epic diff

Run from the epic worktree:

```
cd <epic-worktree-path> && git diff $(git merge-base epic/E-NNN main)
```

The base is the merge base, NEVER bare `main`. A bare-`main` diff here folds main's own post-branch commits into the review surface, and the reviewer has no way to tell them from the epic's work -- in E-278 exactly that produced an 85-line phantom finding against a file no story touched. See Step 8 sub-step 3.

If the diff is empty (no changes relative to the merge base), report "No changes in epic worktree to review" and proceed to Step 1b.

#### Build the story manifest

Assemble a story manifest from the epic's Stories table: list each story ID, title, and a one-line summary of what it implemented (drawn from the story's Description or the implementer's completion report). This gives the code-reviewer cross-story context without requiring it to read every story file.

#### Route to code-reviewer

Send the integration review assignment to the code-reviewer via `SendMessage` with: the epic worktree path, story manifest (IDs, titles, one-line summaries), full Technical Notes, Goals and Success Criteria, and the full epic diff. Include "Review round: 1 of 2 (circuit breaker)" and instructions to focus on cross-story interactions, naming consistency, import conflicts, and architectural issues. PM applies the same AC×surface enumeration described in the AC verification note (Phase 3 Step 5); see the AC×surface matrix in `.claude/agents/code-reviewer.md` (Priority 1).

**Large epic handling**: If the diff exceeds ~3,000 lines, replace inline diff with a per-story file summary (file paths, modified/new status, +/- line counts). Generate from cross-referencing each story's `## Files Changed` with `git diff --stat $(git merge-base epic/E-NNN main)` (merge base, not bare `main`). The reviewer can request specific file contents from the main session.

#### Triage, remediation, and circuit breaker

Triage findings using the same rules as Phase 3 Step 5 item 3. Remediate valid findings via the **Remediation Spawn Context** (defined at the start of Phase 5).

PM records dispositions. If NOT APPROVED, send Round 2 to the code-reviewer with round 1 findings and the updated diff. Max 2 rounds -- if round 2 still has MUST FIX, escalate to the user: (a) fix, (b) retry (resets breaker), (c) override to Step 1b, (d) abandon.

After the Closure CR Integration Review completes (clean, remediated, or user override), proceed to Step 1b.

### Step 1b: Full-suite green gate (unconditional)

Every epic closure is gated on a green full test suite -- `python -m pytest tests/` must report 0 failed in the **main checkout with the epic's changes applied** before the closure is finalized. This is the closure-time verification pass that makes "a closed epic has a green test suite" an executable invariant rather than inert policy (see `.claude/rules/workflow-discipline.md`, Full-Suite-Green Closure Gate). It is **unconditional** -- it runs on every epic closure regardless of what the epic touched. (For epics whose stories modify only context-layer files and no `src/`/`tests/`, the suite still runs -- it confirms no incidental breakage and costs ~90s.)

**Why it runs in Step 8, not here.** The per-story "no pytest in the worktree" rule (the Phase 3 Step 5 item 2 code-reviewer template and `.claude/agents/code-reviewer.md` Test Execution Constraint) exists because a worktree pytest run exercises the worktree's own uncommitted `src/`, not the merged tree the epic closes against -- so a per-story worktree run is not authoritative about the closure state. The only point at which pytest is authoritative for *this epic* is after Step 8's `git apply --3way` patches the epic's accumulated changes onto main. Running the gate here (before Step 8) would test main's *pre-epic* code -- meaningless. The reconciliation is therefore real, not a loophole: the per-story ban stands, and the one authoritative full-suite run happens at closure, in main, after the merge.

**Mechanics live in Step 8.** The actual `python -m pytest tests/` invocation is wired into the Step 8 closure sequence (a sub-step between `git apply --3way` and the commit approval gate): the code-reviewer runs the suite against the main checkout once the epic's changes are applied, and a red suite **aborts the closure commit** and routes the failures into the closure remediation mechanics -- triage per Phase 3 Step 5 item 3, remediate valid findings **serially** via the **Remediation Spawn Context** (in the epic worktree), re-stage and re-apply, then re-run `python -m pytest tests/` until it reports 0 failed. The 2-round circuit breaker applies: if the suite is still red after 2 remediation rounds, escalate to the user with the failure summary and options (a) fix, (b) retry (resets breaker), (c) override and proceed, (d) abandon.

**Where and when the COMPLETED status flip happens.** PM authors the COMPLETED status transition in the **epic worktree's** `epic.md` (not the main checkout), during Step 8 sub-step 3 staging -- *before* sub-step 4 generates and applies the closure patch. This placement is forced by the `.claude/hooks/worktree-guard.sh` hook: while the epic worktree exists (dispatch is active), the hook blocks ALL PM Write/Edit to the main checkout (no agent-memory exception), so PM cannot flip COMPLETED -- or write its Active→Archived `MEMORY.md` flip -- in main; instead PM authors BOTH in the worktree copy (`epic.md` and `.claude/agent-memory/product-manager/MEMORY.md`), and they ride the closure patch into main via sub-step 4's `git apply --3way`. Because the flip is authored in the worktree before sub-step 3, COMPLETED is *set on disk* before this gate runs at sub-step 5. That is intentional and safe: the binding invariant is enforced on the **commit**, not the on-disk string. **The closure commit MUST NOT happen until `python -m pytest tests/` reports 0 failed in main with the epic applied** (or the user explicitly overrides per the circuit breaker). A red gate aborts the commit *and* reverts the applied patch (sub-step 5 failure path), so the worktree's COMPLETED flip never reaches committed main -- COMPLETED is never *finalized* on a red suite. Step 2 performs all other closure bookkeeping (Stories table, History entry, scorecard, Step 3/3a assessments); only the COMPLETED flip itself is authored later, at sub-step 3 in the worktree.

### Step 1d: Closure runtime smoke (conditional)

The reports flow's **first live runtime gate at closure**. Every other closure pass reasons about *code* -- Step 1a audits invariants, Step 1c reviews the diff, Step 1b runs the unit suite -- but none of them ever *runs the reports product against real data*. That gap is how a physically-impossible first-pitch-strike stat reached a live report and a rest-day UTC bug slipped between two epics that both closed green: the unit suite was green in both cases because neither bug is visible without generating a report against the live DB and reading what came out. Step 1d closes that gap.

Like Step 1b, this pass is **defined here but its mechanics live in Step 8** (wired in as sub-step 5b, immediately after the Step 1b full-suite gate) -- it runs in the **main checkout, post-`git apply --3way`**, so the epic's changes are live. The epic worktree has no `bb`, no Docker, no `.env`, and no `data/`, so it cannot run there.

**Conditional trigger (the code-reviewer self-evaluates it).** Unlike Step 1b (unconditional), Step 1d runs only when the epic's closure diff touches a runtime surface. The main session assigns Step 1d **unconditionally**; the code-reviewer runs the trigger read **itself** and reports "Step 1d not triggered" when nothing matches -- routing that read through the main session would be a `dispatch-pattern.md` domain-work violation (inspecting what was built). The read is:

```
cd <epic-worktree-path> && git diff --cached --stat $(git merge-base epic/E-NNN main)
```

(The staged closure diff, against the same base the closure patch uses at sub-step 3. The planning-time AC named `main`; it is adapted to the merge-base base E-260 made the closure-diff standard, so the trigger reflects only the epic's own changes, not main's post-branch divergence.) Step 1d FIRES when any changed path is under a **trigger path**:

- **Runtime code:** `src/reports/`, `src/db/`, `src/api/`, `src/gamechanger/loaders/`, `src/gamechanger/parsers/`, `migrations/`.
- **Build inputs** (a dependency- or build-only epic still changes what the app *runs*, so it must smoke too): `requirements.txt`, `requirements.in`, `requirements-dev.txt`, `requirements-dev.in`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.python-version`.

Without the build-input paths a pure dependency-refresh epic -- exactly the kind most likely to break `uvicorn`/FastAPI startup that pytest never exercises -- would not trigger Step 1d at all, an inverted gate.

**The smoke fixture (`.smoke-fixture`).** The reviewer reads a gitignored two-field `.smoke-fixture` file at the repo root -- **NOT `.env`**. (`.claude/hooks/secret-read-guard.sh` denies any Bash command literally naming `.env*` or `secrets/**`, so a fixture stored there would be unreadable by the reviewer that must read it.) Both fields hold LSB's own real identifiers; **neither is committed** (the file is in `.gitignore`). Two labeled fields, parsed literally:

```
generate=<public_id>
morning-run=<lsb-url-1> <lsb-url-2> ...
```

Read `generate` with `grep '^generate='` and `morning-run` with `grep '^morning-run='`. See `docs/admin/production-deployment.md` (story 10, docs-writer) for the operator-facing setup of this file and the full smoke procedure; this skill references that doc rather than duplicating it.

**Fixture requirement (the `generate` target).** The `.smoke-fixture` `generate` target MUST be a GC team page with **high play-by-play coverage**: against a plays-poor corpus the `reconcile-scoreboard` reading is vacuous, which is precisely the failure class this step exists to close. The skill documents the requirement only; **the actual team identifier stays in the gitignored `.smoke-fixture` file** (operator-owned -- real GC identifiers never enter tracked skill text). **Bootstrap (one-time, operator-owned):** when the operator pins the fixture team, verify its play-by-play coverage in the dev DB -- a count of games that actually carry play-by-play rows (data-bearing, not a bare games count, since scored-but-empty games are the modal case).

**The terminal/static half of that requirement was RETIRED 2026-07-26 with the ratchet.** The fixture also had to be a *terminal* team -- a completed season gaining no further games -- for exactly one reason: a static corpus meant a closure's `generate` ingested no net-new plays, so the post-generate reading could not false-trip the one-way ratchet against a baseline captured before it. With no gate to false-trip, nothing turns on staticness or on the generate -> reconcile-scoreboard order. The currently pinned fixture happens to be terminal and stays as it is; this retires the constraint on a future re-pin, and asks for no operator action now.

**Preflight (env-FAIL, not epic-FAIL).** Step 1d opens with a preflight and does NOT enter the remediation loop on a preflight failure. The preflight requires:

- `.smoke-fixture` present AND **both** fields non-empty (a missing or empty field = env-FAIL);
- the app stack up (see the rebuild rule below);
- credentials live for the profile(s) the smoke actually exercises -- today that is **web only**, so `bb creds check --profile web` (NOT the bare multi-profile `bb creds check`, which exit-0-PASSES on a **mixed** state where a valid mobile profile masks a dead web profile -- and the smoke's `bb report generate` uses the web profile). This is deliberately not a command-side fix: making multi-profile fail on ANY dead profile would break the legitimate "any valid profile = usable" contract. If a future smoke step exercises mobile, extend the preflight to that profile then.

(A fourth requirement -- the reconciliation baseline file being present -- retired 2026-07-26 with the ratchet gate. Nothing reads the baseline any more.)

**A preflight failure escalates to the user and HOLDS the closure -- it is an env-FAIL and does NOT route into the remediation loop.** Expired credentials or an absent fixture are operator-environment problems, not epic defects; feeding them into the remediation loop would manufacture false remediation rounds against the implementer. Only **post-preflight** failures -- a physically-impossible stat, a reference-date mismatch, a non-zero `self_games`, an app that does not answer `/health`, a morning-run crash -- are **epic-FAILs** that route into the closure remediation loop exactly like a red suite (triage per Phase 3 Step 5 item 3, remediate serially via the **Remediation Spawn Context**, 2-round circuit breaker, escalate to the user on the third round).

**Rebuild, not start (build-input epics).** The preflight's "stack up" is a **rebuild** (`docker compose up -d --build app`, per `.claude/rules/app-troubleshooting.md`), not a bare start, whenever the closure diff touches a build input (the second trigger-path group above). Starting a stale image and passing `curl /health` proves the OLD image is healthy, not the epic's. E-256 is the live example: story 07 crosses a starlette MAJOR (0.41.3 -> 1.3.1), and pytest never exercises `uvicorn`/FastAPI startup, so only a rebuilt image proves the app still boots.

**Reinstall the main-checkout Python env (dependency epics), distinct from the image rebuild.** BOTH are required when the closure patch changes `requirements.txt`/`requirements-dev.txt`: the Step 1d commands (`bb report generate`, `bb report morning-run`, `bb report reconcile-scoreboard`) run on the **local interpreter**, not inside the Docker image, so a rebuilt image alone leaves them running against the pre-epic dependency set. The main-checkout env is reinstalled from the patched lockfile **before** the Step 1b full-suite gate and before Step 1d -- this is **sub-step 4b** of the closure sequence. The image rebuild fixes the app that `curl /health` hits; the reinstall fixes the CLI everything else runs on.

**The runtime checks (post-preflight).** Run against the **LIVE dev DB, not a fixture DB** -- a fresh fixture DB is empty, so `reconcile-scoreboard` would pass **vacuously**, precisely the failure class Step 1d exists to close. Order matters where noted:

1. **`bb report generate <generate public_id>`** -- run it before `reconcile-scoreboard` so the scoreboard reads the state the smoke just produced. Since the ratchet retired, this ordering is a convenience rather than a constraint; nothing false-fails if it is broken.
2. **Headline invariant:** the report's `reference_date` equals **today in the operating timezone** (story 05's printed reference-date line is the source of truth; the physically-impossible-stat and rest-day-UTC bugs are exactly what this catches).
3. **`curl /health`** against the running stack (the app answers).
4. **`bb report reconcile-scoreboard --json`** -- assert exactly one thing: **`self_games` == 0**, a hard zero. That is a standing invariant in its own right, not a ratchet, and it is the only assertion this check makes now. **Ignore the command's exit code** -- until the follow-up story strips the vestigial gate, it can still exit non-zero from a diff against the frozen `.project/baselines/reconciliation-scoreboard.json`, and that verdict means nothing. Read the printed table for a sanity impression if you like, but do not fail the closure on any figure other than `self_games`.
5. **`bb report morning-run --dry-run <morning-run urls>`** -- assert **exit 0 ONLY**. Do NOT assert games-found or slots-resolved. This step writes nothing and is **order-independent** -- run it any time after `curl /health`, NOT inside the generate -> reconcile-scoreboard ordering.

**Honest limitation of the morning-run step (stated, not oversold).** On an arbitrary closure date LSB usually has no games, so the resolution ladder does not fire and `--dry-run` skips the real-run alerting preflight. What morning-run reliably gates is the **entry-point wiring + the schedule-read API path + the `operating_today()` timezone-filter plumbing** -- a forward-feature surface `generate` never touches, but shallower than the resolution ladder. Do NOT try to deepen it with a hardcoded `--date`.

**No aggregate-integrity sub-check (E-259).** E-259 dropped the stored `player_season_*` tables and moved season totals to query-time derivation, so there is **no aggregate-integrity gate** to run here -- the aggregate IS the query, and `bb report verify-aggregates` no longer exists. This is a deliberate net shrinkage, not a hole to fill, and nothing moves into the vacated slot. What survives in check 4 is narrower still since the 2026-07-26 ratchet retirement: a single `self_games == 0` assertion, not a fidelity gate. Honest limitation either way: whole-game plays idempotency means the scoreboard cannot see an ingestion-parser change until data is re-ingested, so Step 1d never proved a parser change reconciles -- only that the flow runs and the *current* data still does.

After Step 1d passes (or is not triggered, or the user overrides on the third remediation round), the closure sequence proceeds to sub-step 6 (archive rename).

### Step 2: Update the epic completely

Route to PM, who performs:

- Confirm all story file statuses are DONE.
- Epic Stories table reflects current reality (all rows DONE).
- History entry added with the completion date and a summary of what was accomplished.

**Note on the COMPLETED status flip:** PM does NOT set the epic status to COMPLETED here at Step 2, and does NOT set it against the main checkout at all. PM authors the COMPLETED flip in the **epic worktree's** `epic.md` during Step 8 sub-step 3 staging (before the closure patch is generated), so it rides the patch into main. Reason: at Step 8 the `.claude/hooks/worktree-guard.sh` hook is in dispatch-active mode and blocks ALL PM Write/Edit to the main checkout (no agent-memory exception), so PM cannot flip COMPLETED -- or write its Active→Archived `MEMORY.md` flip -- in main; PM authors both in the worktree copy freely, and they ride the closure patch. COMPLETED is thus *set on disk* before the Step 8 sub-step 5 green gate, but is never *committed* on a red suite: a red gate aborts the commit and reverts the applied patch. The bookkeeping above (Stories table, History entry, scorecard below, and the Step 3/3a assessments) is performed here at Step 2; only the epic-status transition to COMPLETED is authored later, at Step 8 sub-step 3 in the worktree.
- Record a review scorecard table in the epic's History section using this format:

```
### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-NNN-01 | N | N | N |
| Per-story CR -- E-NNN-02 | N | N | N |
| Closure CR Integration Review | N | N | N |
| Codex code review | N | N | N |
| **Total** | **N** | **N** | **N** |
```

Only include rows for review passes that actually ran. Per-story CR rows show aggregated finding totals across all review rounds for that story (e.g., if round 1 had 3 MUST FIX and round 2 had 1, the row shows 4 findings total). The Closure CR Integration Review row shows findings from Phase 5 Step 1c (it is unconditional, so this row always appears); the Codex row shows findings from Phase 4. If the "and review" modifier was not specified, omit the Codex row only -- the Closure CR Integration Review still ran. Reconstruct finding counts from triage summaries recorded during each story's review loop and the closure review passes.

- Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information out of epic files.

### Step 3: Documentation assessment

Per `.claude/rules/documentation.md`. If any trigger fires, spawn docs-writer before archiving. Otherwise record "No documentation impact."

### Step 3a: Context-layer assessment

Per `.claude/rules/context-layer-assessment.md`. Eight triggers, explicit yes/no verdicts in epic History. If any fires, spawn claude-architect before archiving. claude-architect's codification -- including updates to its OWN `.claude/agent-memory/` files -- is authored in the **worktree copy** (the dispatch-active hook denies main-checkout Write/Edit with no agent-memory exception), so it rides the closure patch.

### Step 4: Review ideas backlog

PM checks `/.project/ideas/README.md` for CANDIDATE ideas unblocked by epic completion.

### Step 5: Review vision signals

PM checks `docs/vision-signals.md` for unprocessed signals. Advisory, not blocking.

### Step 6: Present a summary to the user

Before closure merge: epic ID/title, stories completed, review outcomes (per-story CR: N stories reviewed; CR integration: clean/N fixed/not run; Codex: clean/N fixed/skipped/not run), file list (`git diff --stat $(git merge-base epic/E-NNN main)` from the epic worktree -- merge base, not bare `main`, or the summary you show the user will list files main changed and this epic did not), key artifacts, follow-up work, promotable ideas.

### Step 7: Shut down implementers and code-reviewer

Send a `shutdown_request` to each implementer and to the code-reviewer. Wait for shutdown confirmations. **Do NOT shut down PM yet** -- PM is needed for memory updates after archive.

**After spinning down implementers and code-reviewer:**

### Step 7a: Ancillary file sweep

Stage any main-checkout session artifacts before the closure merge. During dispatch, agents write to the epic worktree (those changes are captured by Step 8's worktree patch). This step stages main-checkout changes: vision signals from the main session, leftover planning artifacts, or idea captures. These staged files are included in Step 8's closure commit alongside the worktree patch -- no separate commit is made here. **Stage, do not commit**, for two reasons. First and binding: the closure is ONE atomic commit (`dispatch-pattern.md`), and a Step 7a commit would advance main's HEAD so these files land outside it. Second: a path present in both trees could then be clobbered or conflict when sub-step 4 applies the epic patch onto the advanced main.

**Citation corrected in E-278**: this sentence used to say a Step 7a commit "would cause Step 8's `git diff --cached main` to generate reverse patches for the committed files." Sub-step 3 diffs against `$(git merge-base epic/E-NNN main)`, and **the merge base does not move when main advances** -- so that specific mechanism no longer fires, while the atomicity reason above binds unchanged. The instruction is the same; only its stated reason was stale.

**Preflight**: Run `cd /workspaces/baseball-crawl && git status --porcelain` (without `-uall`). If the output is empty, skip this step silently and proceed to Step 8.

**Enumerate main-checkout changes**: Use the TN-8 approach to identify ancillary artifacts:

1. **Recognized artifact paths** (stage these):
   - `docs/vision-signals.md` (if modified) -- single file, `git add docs/vision-signals.md`
   - `.claude/agent-memory/` (**pre-dispatch** leftover planning artifacts not committed by plan skill Step 2a, if any -- dispatch-time and closure-time own-memory writes ride the worktree/closure patch, not this main-checkout sweep) -- mixed directory, enumerate with:
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

Merge the epic worktree's accumulated changes into the main checkout and produce a single atomic commit that contains the applied patch (which carries the COMPLETED flip and PM's Active→Archived memory update) and the archive rename.

**Closure sequence:**

1. **Migration merge-time scan:** If the epic includes new migrations AND main has added migrations since the worktree branched, flag the numbering conflict to the user before proceeding.

2. **Clean-tree preflight:** Verify the main checkout has no unstaged or untracked changes. Step 7a may have legitimately staged ancillary files, so check unstaged/untracked only:
   ```
   cd /workspaces/baseball-crawl && git diff --name-only     # unstaged modifications
   cd /workspaces/baseball-crawl && git ls-files --others --exclude-standard  # untracked files
   ```
   If either command produces output, report the unexpected changes to the user and wait for instructions before proceeding. Do NOT proceed with `git apply` on a dirty working tree -- it may silently merge unrelated changes into the epic commit. Staged files from Step 7a are expected and will be captured in the closure commit.

3. **Stage and diff the epic worktree:** `cd <epic-worktree-path> && git add -A` (stage all accumulated changes), then `git diff --binary --cached $(git merge-base epic/E-NNN main) > /tmp/E-NNN-epic.patch`.

   ⚠️ **The base is `$(git merge-base epic/E-NNN main)`, NEVER `main` — and this is the one command in the sequence whose wrong form is SILENT and DESTRUCTIVE.** `main` moves while an epic runs (the operator commits to it; other epics close onto it). A diff against a moved `main` reports MAIN's own post-branch divergence as if it were the epic's, in the REVERSE direction — so applying that patch **silently reverts commits nobody in this epic touched**, and the resulting closure commit looks entirely normal. Nothing downstream tests for it: sub-step 4's `git apply --check` passes (the reversal applies cleanly), sub-step 5's full suite passes (main's reverted change is usually not what the epic's tests cover), and the staged diff you present at sub-step 8 shows the reversal as an ordinary hunk. **The merge base is the only base under which the patch contains exactly the epic's own changes.**

   The failure is not hypothetical and it does not require using the wrong command *here*: at E-278's closure the main session ran a post-staging sanity diff against `main` instead of the merge base, and it surfaced an 85-line change to `.claude/hooks/send-message-counter.sh` — a context-layer file no story in that epic authorized, which is exactly the shape that should stop a closure. It was a phantom: the operator had committed that hook change to `main` (`c990446`) after the epic branched. Every individual observation in the finding was accurate; the BASELINE was wrong. **So the merge base binds every diff you take during closure, not just the patch-generating one** — a `main`-based sanity check manufactures phantom findings that halt a good closure, and a `main`-based patch ships a silent revert. Sub-step 2's clean-tree preflight does not catch either: it inspects the main checkout's working tree, and this defect is entirely in the patch's contents.

   **The discriminator is WHICH TREE you are standing in, so do not "fix" every `main` in this file.** In the **main checkout**, `main` IS `HEAD`, so `git diff --cached main` there (sub-step 8's operator presentation) is a staged-vs-HEAD diff and is correct. In the **epic worktree**, `HEAD` is `epic/E-NNN` and `main` is a tip that has moved since the branch point — every worktree-relative `main` in a diff is the hazard above. Rule: **`main` as a diff base is safe only where it equals `HEAD`; everywhere else use `$(git merge-base epic/E-NNN main)`.**

4. **Dry-run then apply the patch on main:** `cd /workspaces/baseball-crawl && git apply --check --3way /tmp/E-NNN-epic.patch`. If the dry-run succeeds, run `git apply --3way /tmp/E-NNN-epic.patch` to apply for real.

4b. **Dependency-refresh reinstall (conditional -- Phase 5 Step 1d, AC-4c):** If the applied patch changed `requirements.txt` or `requirements-dev.txt`, reinstall the **main-checkout** Python env from the patched lockfile BEFORE sub-step 5 (and thus before the Step 1d smoke at sub-step 5b): `cd /workspaces/baseball-crawl && pip install -r requirements-dev.txt && pip install --no-deps -e .` (the editable install per the devcontainer convention). The epic worktree cannot install into the main checkout, so nothing else forces this -- without it, sub-step 5 would run the epic's code against the *pre-epic* dependency set and pass green. This is distinct from the Docker image rebuild the Step 1d preflight performs: the rebuild fixes the app that `curl /health` hits; this reinstall fixes the local interpreter that `bb`/pytest run on. Skip this sub-step when the patch changed neither lockfile.

5. **Full-suite green gate (`python -m pytest tests/`):** This is the authoritative execution of the Phase 5 Step 1b closure gate -- it runs here because the epic's changes are now applied to main (after sub-step 4) and pytest is finally authoritative for this epic. Spawn the code-reviewer to run `cd /workspaces/baseball-crawl && python -m pytest tests/`. It is **unconditional** (runs on every closure).
   - **0 failed**: the applied patch (sub-step 4) already carries the worktree's COMPLETED flip authored at sub-step 3 -- the green gate has passed, so that COMPLETED flip is now cleared to be committed. Proceed to sub-step 6.
   - **Any failures**: do NOT commit. The applied patch (sub-step 4) carries the worktree's COMPLETED flip, so reverting the patch reverts COMPLETED along with it -- COMPLETED is never *committed* on a red suite. At this point sub-step 4's `git apply --3way` is the only main-checkout change (the archive rename in sub-step 6 has NOT run yet; PM's Active→Archived memory flip rides the patch and is reversed by the `git apply -R` below, along with COMPLETED), so the minimal reset is `cd /workspaces/baseball-crawl && git reset HEAD && git apply -R --3way /tmp/E-NNN-epic.patch` (unstage, then symmetrically reverse the applied patch). Use `git apply -R`, NOT `git checkout -- .`: the reverse-apply reverses the patch INCLUDING any files it created, so the subsequent re-apply after remediation does not error on already-present/untracked files. `git checkout -- .` would only restore tracked files to HEAD and would leave patch-created untracked files (e.g. a new migration) behind, deadlocking the re-apply. The reverse-apply also restores main's `epic.md` to its ACTIVE on-disk status. Do NOT run the archive-undo `git mv` from sub-step 9 reject path (c) -- there is no archive rename to undo at sub-step 5, and that `git mv` would fail on a non-existent directory. Then route the failures into the closure remediation mechanics -- triage per Phase 3 Step 5 item 3, remediate valid findings **serially** via the **Remediation Spawn Context** (in the epic worktree), then re-run the closure sequence from sub-step 3 (re-stage, re-diff, re-apply) and re-run pytest until it reports 0 failed. The 2-round circuit breaker applies: if still red after 2 remediation rounds, escalate to the user with the failure summary and options (a) fix, (b) retry (resets breaker), (c) override and proceed, (d) abandon.

   This run is a **hard precondition on the closure commit**: the closure commit (sub-step 10) MUST NOT proceed until `python -m pytest tests/` reports 0 failed in the main checkout with the epic's changes applied (or the user explicitly overrides per the circuit breaker). This is the authoritative execution of the Phase 5 Step 1b gate -- not an advisory check. On a green suite the sequence proceeds to sub-step 5b (the Phase 5 Step 1d closure runtime smoke) before the sub-step 6 archive rename -- the "0 failed" branch above reaches sub-step 6 *through* 5b, it does not skip it.

5b. **Closure runtime smoke (`bb report generate` + `reconcile-scoreboard` + `morning-run --dry-run`):** The authoritative execution of the **Phase 5 Step 1d** gate -- see Step 1d for the full procedure, trigger paths, fixture format, and honest limitations. **Conditional:** the code-reviewer first runs the trigger read **itself** -- `cd <epic-worktree-path> && git diff --cached --stat $(git merge-base epic/E-NNN main)` -- and reports "Step 1d not triggered," skipping straight to sub-step 6, when no changed path is under a Step 1d trigger path (the main session does not perform that read -- it is domain work). When triggered, the reviewer runs the Step 1d preflight and runtime checks in the **main checkout** against the LIVE dev DB. A **preflight** failure (env-FAIL) -- absent/empty `.smoke-fixture` field, stack down, dead credentials -- **escalates to the user and holds the closure; it does NOT enter the remediation loop.** A **post-preflight** failure (epic-FAIL) -- reference-date mismatch, `self_games > 0`, `/health` down, a `morning-run --dry-run` non-zero exit -- **aborts the closure commit** and routes into the closure remediation mechanics exactly like a red suite (triage per Phase 3 Step 5 item 3, remediate serially via the **Remediation Spawn Context**, re-run the closure sequence from sub-step 3, 2-round circuit breaker, escalate to the user on the third round). On pass (or not-triggered, or user override), proceed to sub-step 6.

6. **Archive rename:** `git mv epics/E-NNN-slug/ .project/archive/E-NNN-slug/` in the main checkout. The rename happens on disk before staging so that `epics/*/epic.md` no longer contains a `COMPLETED` epic file at commit time -- this is what allows a single atomic commit to clear `.claude/hooks/epic-archive-check.sh`.

7. **PM memory update (authored earlier, in the worktree):** PM's Active→Archived `MEMORY.md` flip -- and any closure topic-file flushes (`archived-epics.md`, `epic-codifications.md`, numbering-state) -- were authored in the **worktree copy** during the sub-step-3 authoring window, alongside the COMPLETED `epic.md` flip, so they ride the sub-step-3 patch into main via sub-step 4's `git apply`. There is no separate main-checkout memory write here: the dispatch-active hook denies ALL main-checkout Write/Edit (no agent-memory exception), so every closure-time own-memory write MUST be authored in the worktree. (claude-architect's Step-3a closure codification, including its own agent-memory, is authored in the worktree for the same reason.)

8. **Stage on main:** `cd /workspaces/baseball-crawl && git add -A` (stage the applied patch -- which already carries PM's memory update -- and the archive rename together). The pre-commit PII scan runs automatically on the subsequent `git commit`.

9. **Pause for explicit user approval.**

   **Present staged changes**: Run `git diff --cached --stat main` and present the file count and insertion/deletion totals to the user. No path filter -- `git diff` alone would miss the already-staged changes, which are most of the closure.

   ⚠️ **`main` is CORRECT here and must NOT be "fixed" to a merge base.** This is the one closure diff taken in the **main checkout**, where `main` IS `HEAD`, so it is a staged-vs-HEAD diff and shows exactly what the pending commit contains. The merge-base rule in sub-step 3 applies to diffs taken in the **epic worktree**, where `HEAD` is `epic/E-NNN` and `main` is a tip that has moved since the branch point. The general rule: **`main` as a diff base is safe exactly where it equals `HEAD`.** (E-278 swept the worktree-relative sites to the merge base and deliberately left this one; do not include it in a future sweep.)

   **User approval**: Wait for the user to respond with exactly one of "yes", "commit", "approve", or "go ahead". Any other response -- including silence, questions, or ambiguous acknowledgments ("looks good", "ok", "sure", "👍") -- does NOT count as approval. Do not proceed to the `git commit` sub-step (sequence step 10) until an explicit approval word is received.

   **User rejects**: The main checkout is half-closed at this point (the patch was applied in sub-step 4 -- carrying PM's Active→Archived memory flip -- the full-suite gate passed in sub-step 5, and the archive rename happened in sub-step 6 -- all before the approval gate). Three reject paths:

   - (a) **'commit' to resume**: The user changed their mind. Proceed to sub-step 10 normally.
   - (b) **inspect**: Hold the staged state and let the user review. Do not commit. When the user is ready, they can return to (a) or (c).
   - (c) **'abort'**: Individually reverse the two Step-8 closure actions -- the applied patch (sub-step 4), which carries PM's Active->Archived memory flip and reverses it too, and the archive rename (sub-step 6) -- while PRESERVING every Step 7a ancillary edit (vision-signals, ideas, AND any pre-dispatch `.claude/agent-memory/` plan-leftover edits -- see Step 7a item 1). Those legitimately predate Step 8 and are the only main-only edits that survive. Do NOT use `git checkout -- .` here: it reverts ALL tracked modifications to HEAD, which would irreversibly destroy the staged Step 7a edits, and it would leave patch-created untracked files behind. The main session runs the git reset sequence:
     ```
     cd /workspaces/baseball-crawl && git reset HEAD                    # unstage everything (all Step 7a edits stay present in the working tree)
     cd /workspaces/baseball-crawl && git mv .project/archive/E-NNN-slug/ epics/E-NNN-slug/  # reverse the archive rename (sub-step 6), restoring the patch's epics/ paths
     cd /workspaces/baseball-crawl && git apply -R --3way /tmp/E-NNN-epic.patch  # symmetrically reverse the applied patch (sub-step 4), removing any files it created
     ```
     The `git mv` back MUST precede the reverse-apply so the epic files are at their `epics/` patch paths when `git apply -R` reverses them.

     After the reset, the applied patch (including any files it created and PM's memory flip it carries) and the archive rename are all reversed, and every Step 7a ancillary edit (vision-signals, ideas, and any pre-dispatch agent-memory plan-leftover edit) remains (as working-tree modifications). The epic worktree is preserved for manual recovery. Step 9 (worktree cleanup) is skipped on the abort path -- it only runs after a successful closure commit.

   If the pre-commit PII scan catches issues during sub-step 10's `git commit`, nothing is committed (the hook blocks the commit before any state change), but the staged half-closed state remains; treat the same as (b) inspect or (c) abort.

10. `git commit -m "feat(E-NNN): <epic title>"`. The single commit atomically contains the applied patch (which carries PM's memory update) and the archive rename.

**Dry-run fails**: Present conflict report. User decides: (a) resolve manually and retry, or (b) abort (worktree preserved).

### Step 9: Worktree cleanup

After the closure commit succeeds, remove the epic worktree and its branch:

```
cd /workspaces/baseball-crawl && git worktree remove --force /tmp/.worktrees/baseball-crawl-E-NNN && git branch -D epic/E-NNN
```

The `--force` flag is required because the epic worktree still has staged changes from the closure merge sequence (those changes were patched onto main in Step 8 sub-steps 4-8 but never committed back to the `epic/E-NNN` branch). Without `--force`, `git worktree remove` exits with "contains modified or untracked files, use --force to delete it." The forced removal is safe because the closure commit on main already captures the same content.

Verifiable: after this step, `ls /tmp/.worktrees/` does not include `baseball-crawl-E-NNN/` and `git branch --list 'epic/E-NNN'` is empty.

### Step 10: Shut down PM

Send PM an explicit `shutdown_request` and wait for confirmation. Team teardown is automatic on session exit -- there is no explicit delete step.

### Step 11: Post-shutdown reconciliation sweep

PM writes `.claude/agent-memory/**` during closure (its Active→Archived `MEMORY.md` update is authored in the worktree at sub-step 3 and captured by the closure patch), but a final memory flush can land *after* the Step 8 closure commit -- as PM spins down at Step 10. After PM is shut down, re-run `cd /workspaces/baseball-crawl && git status --porcelain`:

- **Tree clean**: done.
- **Only `.claude/agent-memory/**` stragglers remain** (files written by agents that ran in this dispatch): fold them into the closure commit with `cd /workspaces/baseball-crawl && git commit --amend --no-edit` (safe while unpushed), then confirm the tree is clean.
- **Any remaining change is outside `.claude/agent-memory/**`** (a new, unrecognized, or non-memory file): do NOT amend silently -- report it to the user and wait for instructions per the Step 8 sub-step 9 approval gate.

**Narrow carve-out, not a loophole**: identical scope to the plan skill's Step 2b -- a deliberate exception to the "do not commit automatically / require user approval" gate (Anti-Pattern 4 and Step 8 sub-step 9), limited to a late flush of the *same pre-approved artifact class* (`.claude/agent-memory/**`) completing the *same logical unit* already inside the approved closure commit. The root cause is a timing race (async memory flush vs. the staging snapshot), so this is a post-shutdown reconciliation sweep, not a replacement for the approval gate. New or unrecognized files still require the user-approval pause.

### Step 12: The terminal gate -- closure is a checked END-STATE, not a step list

**"Closure complete" may not be reported until command output shows all five of these.** Not "I ran the steps" -- the observed end state:

```
cd /workspaces/baseball-crawl
git worktree list                    # main only; no baseball-crawl-E-NNN entry
git branch --list 'epic/E-NNN'       # empty
ls .project/archive/E-NNN-slug/      # the epic directory is archived
git status --short                   # clean
```
plus PM confirmed shut down (Step 10).

This extends the shape Step 9 already uses ("Verifiable: after this step...") across the whole of steps 7-11, because that is where the sequence actually breaks. In E-276 the hub skipped steps 7 through 11 outright -- the second procedure skip in the same epic -- and its own diagnosis names the cause: *"I treated the procedure as a list of things to report on rather than a sequence to execute."* A procedure recalled from ambient or post-compact memory is a RELAYED procedure, and the same rule applies to it as to any other relay: check it against the artifact. Here the artifact is the repository state, and these five commands are how you read it.

If any check fails, closure is NOT complete: finish the missing step, then re-run the gate.

---

## Workflow Summary

```
Prerequisites -> Phase 0 (tmux) -> Phase 1 (team composition) -> Phase 2 (dispatch setup)
  |
  v
Phase 2: Create epic worktree -> team forms implicitly on first spawn -> spawn agents (all in epic worktree, no isolation) -> PM sets ACTIVE
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
Phase 4 (if "and review"): Codex code review only (headless -> prompt fallback)
  Codex-first: it runs BEFORE the Phase 5 Closure CR Integration Review; triage + remediation in epic worktree, 2-round circuit breaker
  |
  v
Phase 5: Validate -> Step 1a invariant audit (if any) -> Step 1c Closure CR Integration Review (unconditional, pre-merge, last pre-merge review) -> Step 1b full-suite-green gate (`python -m pytest tests/` in main, unconditional, executed post-merge at Step 8 sub-step 5; reds -> Remediation Spawn Context remediation loop) -> Step 1d closure runtime smoke (conditional on a runtime-surface diff, executed post-merge at Step 8 sub-step 5b; epic-FAIL -> remediation loop, env-FAIL -> escalate and hold) -> PM completes epic -> doc + context-layer assessments -> summary
  -> shut down implementers + CR -> ancillary file sweep (stage session artifacts, user approval)
  -> closure merge and commit (patch -> dry-run -> apply -> archive mv -> PM memory -> approval gate -> single commit)
  -> worktree cleanup -> shut down PM (teardown automatic on session exit)
  -> post-shutdown reconciliation sweep (fold late `.claude/agent-memory/**` stragglers via --amend; narrow carve-out)
  -> Step 12 TERMINAL GATE: closure is complete only when command output shows it
     (worktree gone, branch deleted, epic archived, tree clean, PM shut down)
```

Phase 5 has an entry precondition as well as an exit gate: if "and review" is active, the Codex findings artifact (`/tmp/codex-review-*.txt`, mtime in-session) must EXIST before Step 1c. Absent means Phase 4 did not run -- run it first.

---

## Edge Cases

- **Epic not found / DRAFT / COMPLETED / ABANDONED / BLOCKED**: Report status to user and stop. Do not search the archive for completed epics.
- **No eligible stories**: Report to user (all BLOCKED or all DONE).
- **Spawn fails**: Follow Dispatch Failure Protocol (`workflow-discipline.md`) -- report and ask, do not improvise.
- **No uncommitted changes for review**: the Closure CR Integration Review (Phase 5 Step 1c) reports "No changes in epic worktree to review" and proceeds to Step 1b; if Codex (Phase 4) ran, it likewise has nothing to review.
- **Codex timeout/failure**: Phase 4 degrades to prompt-generation fallback.
- **CR or PM context fills**: Respawn with fresh state summary. No data lost (work products persist on disk).

---

## Anti-Patterns

1. **Do not fall for the "quick check" trap.** The main session MUST NOT: create, modify, or delete any file; verify ACs or update statuses; bypass the code-reviewer; absorb a crashed agent's work; apply fixes -- not even trivial one-line fixes. When something feels too small to route, route it anyway.
2. **Do not proceed to closure with unverified stories.** If any AC is unmet, send the implementer back.
3. **Do not skip the documentation assessment.** The epic cannot be archived until documentation impact is evaluated.
4. **Do not commit automatically.** The user must explicitly approve the closure commit. See the approval gate in Phase 5 Step 8's closure sequence (sequence step 8). The Step 11 post-shutdown reconciliation sweep is the sole, narrow exception: it folds *only* late `.claude/agent-memory/**` flushes (the same pre-approved artifact class, already inside the approved commit) via `--amend`. It does not authorize committing new, unrecognized, or non-memory files without approval.
5. **Do not skip PM spawning.** PM handles all status updates and AC verification during dispatch.
6. **Do not skip the context-layer assessment.** The epic cannot be archived until context-layer impact is evaluated.
7. **Do not defer findings to epic History.** Every finding must reach a terminal state (FIXED or DISMISSED) during the story. No deferral path exists.
8. **Do not dismiss valid findings based on size or cosmetic nature.** If the finding is correct, it gets fixed. "Correct but not worth fixing" is not a valid dismissal reason.
