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
- Any request that implies dispatching an epic's stories for implementation

**Chaining modifier**: The user may append "and review" or "and codex review" to any trigger phrase (e.g., "implement E-NNN and review", "start E-NNN and codex review"). This chains a code review after implementation completes. See Phase 4.

---

## Purpose

Codify the full workflow for dispatching and coordinating an epic when the user requests implementation. The main session (user-facing agent) acts as both spawner and coordinator: it reads the epic, spawns implementers directly, assigns stories with full context blocks, monitors completion, verifies acceptance criteria, manages all statuses, cascades to newly unblocked stories, and runs the closure sequence. No PM teammate is spawned during dispatch.

This skill is the primary dispatch procedure reference. It aligns with the canonical model defined in `/.claude/rules/dispatch-pattern.md`.

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

If the session is running inside tmux, rename the current window to the epic ID for easy identification during Heavy mode dispatch. Run this via the Bash tool **before** team creation begins.

**Command** (substitute the actual parsed epic ID for the placeholder -- e.g., `"E-090"`, not the literal string `"E-NNN"`):

```bash
{ [ -n "$TMUX" ] && command -v tmux >/dev/null 2>&1 && tmux rename-window "E-NNN" 2>/dev/null; } || true
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

- **If present and non-empty**: Extract the listed agent types. These are the implementers to spawn. PM is NOT an agent to spawn -- the main session coordinates directly.
- **If absent or empty**: Use the Agent Selection routing table in `/.claude/rules/dispatch-pattern.md` to determine which agent types are needed based on story domains and "Files to Create or Modify" sections. Read story files to make this determination.

### Multi-Wave Planning

Review the full dependency graph across all stories:

- **Single-wave epics** (no inter-story dependencies): All implementers are spawned at once in Phase 2.
- **Multi-wave epics** (stories have dependencies on other stories): Identify which agent types are needed for wave 1 (stories with no unsatisfied dependencies) and which are needed for later waves. Spawn wave-1 agents in Phase 2. Spawn later-wave agents directly as their dependencies complete during Phase 3.

---

## Phase 2: Dispatch

Create the team and spawn implementers. The main session spawns implementers directly -- no PM teammate is spawned.

### Step 1: Create the team

Use `TeamCreate` to create a dispatch team for the epic.

### Step 2: Spawn implementing agents and code-reviewer

Spawn each implementing agent with `isolation: "worktree"` (unless the context-layer exception applies -- see Phase 3 Step 2). This gives each agent an isolated copy of the repository via `git worktree`, preventing concurrent stories from interfering with each other's working trees.

Spawn context:

```
You are a [agent-type] agent on the [team-name] team. Wait for the main session to assign you a story via SendMessage. Do not begin work until you receive your story assignment with the full story file text and Technical Notes.
```

If this is a multi-wave epic, spawn only wave-1 agents now. Later-wave agents are spawned during Phase 3 as dependencies complete (each with `isolation: "worktree"` by default).

**Spawn the code-reviewer** alongside the implementing agents. The code-reviewer is infrastructure, not a story-specific implementer -- it is NOT listed in the epic's Dispatch Team section. The implement skill spawns it automatically for every dispatch that includes implementing agents. The code-reviewer is NOT spawned with `isolation: "worktree"` -- it needs to access any implementer's worktree path to read their changed files and run `git diff`. Spawn context:

```
You are the code-reviewer agent on the [team-name] team. Wait for review assignments from the main session via SendMessage. Do not self-initiate reviews. Each review assignment will include a story ID, the full story file text, epic Technical Notes, and the implementer's Files Changed list. When the implementer worked in a worktree, the assignment will include the worktree path -- use it when reading files and running git diff.
```

### Step 3: Set epic to ACTIVE

If this is the first dispatch of this epic (status is `READY`), update the epic status to `ACTIVE`.

---

## Phase 3: Coordination

The main session owns all coordination during dispatch. This is the core dispatch loop.

### Step 1: Identify eligible stories

Find stories with `Status: TODO` whose blocking dependencies are all `DONE`.

### Step 2: Route stories to agents

For each eligible story:

1. **Check Agent Hint.** If the story has an `## Agent Hint` field, prefer that agent type.
2. **Check context-layer routing.** Scan the story's "Files to Create or Modify" section. If **any** file matches a context-layer path (see Routing Precedence in `/.claude/rules/dispatch-pattern.md`), that story MUST go to `claude-architect` regardless of the Agent Hint. **Isolation depends on file mix:** if the story modifies ONLY context-layer files, spawn WITHOUT `isolation: "worktree"` (runs in the main checkout because these files are shared infrastructure that must be immediately visible to all agents). If the story is mixed (context-layer + code files), spawn `claude-architect` WITH `isolation: "worktree"` -- the architect edits both context-layer and code files from the worktree.
3. **Fall back to routing table.** If no Agent Hint and no context-layer match, use the Agent Selection table in `/.claude/rules/dispatch-pattern.md` to determine the agent type from file paths and story domain.

### Step 3: Update statuses

Mark each eligible story `IN_PROGRESS` in both the story file and the epic Stories table.

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

You are working in a git worktree (an isolated copy of the repository). Review `.claude/rules/worktree-isolation.md` for constraints on what you can and cannot do in a worktree. Key constraints: no Docker commands, no `bb` CLI, no `.env` or `data/` access. You CAN run pytest and edit tracked files.

Satisfy all acceptance criteria and report back when complete. Do NOT update story status files -- the main session handles all status updates.

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

**Context block requirements** (per `/.claude/rules/dispatch-pattern.md`):
- Include the **full story file text** verbatim. Never summarize.
- Include the **full epic Technical Notes** verbatim.
- When a story has completed upstream dependencies with Handoff Context declarations, include the declared artifact paths and descriptions.

Assign stories in parallel when they have no file conflicts.

### Step 5: Monitor, review, and verify

Stay active in the team. As each implementer reports completion (with `## Files Changed`):

1. **Check context-layer-only skip condition.** If the story modifies ONLY context-layer files (`.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/`, `CLAUDE.md`) and no Python code, the main session verifies ACs directly and marks DONE. The code-reviewer is skipped for context-layer-only stories. Proceed to Step 6.

2. **Route code stories to the code-reviewer.** For stories that touch Python code or any non-context-layer files, send the work to the code-reviewer using this template:

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

3. **If the reviewer returns APPROVED** (no MUST FIX findings): Run the merge-back sequence (see Step 5a below), then mark the story `DONE` in both the story file and epic Stories table. Any SHOULD FIX findings from the reviewer are recorded in the epic's History section during closure -- they are NOT relayed to the implementer.

4. **If the reviewer returns NOT APPROVED** (MUST FIX findings): Route ONLY the MUST FIX findings to the implementer with the review round number (e.g., "Round 1 of 2 -- MUST FIX items below"). Do NOT include SHOULD FIX items in the feedback to implementers. The implementer fixes the issues in the same worktree and reports completion again (with updated `## Files Changed`). Send the updated work back to the reviewer for Round 2 using an expanded template that includes the prior findings:

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

Round 1 MUST FIX findings:
[Paste the MUST FIX findings from the round-1 review verbatim]

Review round: 2 of 2 (circuit breaker)

This is a round-2 re-review. The implementer was asked to fix the Round 1 MUST FIX findings listed above. Perform a full re-review of all changed files, but focus on whether the Round 1 MUST FIX items are resolved and whether the fixes introduced any new issues. Report findings using the structured format.
```

5. **Circuit breaker.** Max 2 review rounds per story. If the 2nd review still has MUST FIX findings, escalate to the user with the findings summary and present options:
   - (a) Fix it themselves
   - (b) Tell the implementer to try again (resets the circuit breaker)
   - (c) Override the reviewer and mark DONE (explicit user override -- the user assumes responsibility for unresolved findings)
   - (d) Abandon the story
   The main session does NOT mark the story DONE and does NOT loop further without user direction.

### Step 5a: Merge-back (worktree stories only)

After the code-reviewer approves a story that was implemented in a worktree, the main session runs the merge-back sequence from the main checkout BEFORE marking DONE or cascading. A story is NOT marked DONE until its branch is successfully merged.

**Merge-back sequence:**

1. `git merge --no-ff <worktree-branch>` from the main checkout -- creates a merge commit preserving story history.
2. **If merge succeeds:**
   - Remove the worktree: `git worktree remove <path>` (retry with `--force` if it fails due to untracked files).
   - Delete the branch: `git branch -d <branch>` (safe because the branch is fully merged).
   - Mark the story `DONE` (Step 6).
   - Proceed to cascade (Step 6).
3. **If merge conflicts:**
   - The story remains `IN_PROGRESS`.
   - Cascade is blocked for dependent stories only (non-dependent stories can proceed).
   - The worktree stays active for inspection.
   - Escalate to the user with conflict details: which files conflict and between which stories.
   - The user resolves the conflict in the main checkout (not the worktree).
   - After resolution, the main session removes the worktree, deletes the branch, marks DONE, and proceeds to cascade.

For stories that were NOT implemented in a worktree (context-layer stories), skip this step -- proceed directly to marking DONE.

### Step 6: Cascade

After marking a story DONE, check for newly unblocked stories (stories whose blocking dependencies are now all DONE).

- If the required agent type is already on the team, assign the story directly (repeat from Step 2).
- If a new agent type is needed, spawn the agent and assign the story.
- If no more stories are eligible and some are still in progress, wait for more completions.
- If all stories are DONE, proceed to Phase 4 (or Phase 5 if no review chain).

---

## Phase 4: Optional Review Chain

If the user specified the "and review" modifier (e.g., "implement E-NNN and review"):

- After all stories are verified DONE, chain into the code review workflow at `.claude/skills/codex-review/SKILL.md` (headless path).
- Run the review before proceeding to the closure sequence (Phase 5).
- The main session invokes the review skill directly.

If the modifier was not specified, skip this phase and proceed directly to Phase 5.

---

## Phase 5: Closure Sequence

When all stories are verified DONE (and the optional review chain is complete), execute the following closure sequence in order.

**Before spinning down the team:**

### Step 1: Validate all work

Confirm all stories are DONE. Per-story validation was performed by the code-reviewer during Phase 3 (for code stories) or by the main session directly (for context-layer-only stories). This step confirms reviewer APPROVED status for code stories and main-session verification for context-layer-only stories -- it is not a re-review of all code.

**Worktree verification:** Verify all worktree branches have been merged into the current branch. Run `git branch` to confirm no worktree branches remain unmerged. Then run `git worktree list --porcelain` as a safety-net sweep for orphaned worktrees from error paths. If any orphans are found, force-remove them (`git worktree remove --force <path>`, then `git branch -D <branch>` for unmerged branches). Run `git worktree prune` as a final cleanup for stale registrations. Per-story worktree cleanup happens at merge-back time (Phase 3 Step 5a) -- this closure check catches only orphans from error paths.

### Step 2: Update the epic completely

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

Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`. Instruct an implementing agent still on the team to perform this move. Do not proceed to team shutdown until the archive is confirmed.

### Step 5: Update PM memory

Move the epic from "Active Epics" to "Archived Epics" in the PM's MEMORY.md (`.claude/agent-memory/product-manager/MEMORY.md`). Note any follow-up work or newly unblocked items.

### Step 6: Review ideas backlog

Check `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

### Step 7: Review vision signals

Check whether `docs/vision-signals.md` has any content after the `## Signals` heading. If unprocessed signals exist, mention them in the closure summary and ask the user if they want to "curate the vision." This is advisory, not blocking -- the closure sequence proceeds regardless of the user's answer.

### Step 8: Present a summary to the user

Before ending the dispatch, present a clear summary including:
- Epic ID and title
- List of stories completed (with brief descriptions)
- Key artifacts created or modified
- Any follow-up work identified
- Any ideas that may now be promotable

### Step 9: Shut down all teammates

Send a `shutdown_request` to each implementing agent on the team. Wait for shutdown confirmations. Delete the team.

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
Phase 0: tmux rename-window "E-NNN" (silent, non-blocking)
  |
  v
Phase 1: Read epic's Dispatch Team section
  - Extract implementer types (no PM)
  - Plan multi-wave spawning if dependencies exist
  |
  v
Phase 2: Create team, spawn implementers (with isolation: "worktree") + code-reviewer (no worktree)
  - Context-layer stories: spawned WITHOUT worktree isolation
  - Code-reviewer spawned automatically (not in Dispatch Team, no worktree)
  - Set epic to ACTIVE if currently READY
  |
  v
Phase 3: Coordination loop
  - Identify eligible stories (TODO + deps satisfied)
  - Route to agent type (Agent Hint > context-layer check > routing table)
  - Context-layer stories -> claude-architect, no worktree
  - Mark stories IN_PROGRESS, assign with full context blocks (+ worktree notice)
  - Implementer reports completion with ## Files Changed (worktree-absolute paths)
      |
      v
    Context-layer-only? --YES--> Main session verifies ACs, marks DONE
      |
      NO
      |
      v
    Send to code-reviewer (round 1 of 2, include worktree path)
      |
      v
    APPROVED? --YES--> Merge-back: git merge --no-ff -> remove worktree -> delete branch -> Mark DONE
      |                  (SHOULD FIX -> epic History)
      NO (MUST FIX)      [If merge conflict: escalate to user, block dependent cascade only]
      |
      v
    Route MUST FIX to implementer, implementer fixes in same worktree
      |
      v
    Send to code-reviewer (round 2 of 2)
      |
      v
    APPROVED? --YES--> Merge-back -> Mark DONE
      |
      NO
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
  - Validate all work (confirm DONE + reviewer approved + all branches merged)
  - Sweep for orphaned worktrees (git worktree list --porcelain; force-remove; prune)
  - Update epic to COMPLETED with history entry
  - Documentation assessment (spawn docs-writer if needed)
  - Context-layer assessment (spawn claude-architect if needed)
  - Archive epic to /.project/archive/
  - Update PM memory
  - Review ideas backlog
  - Review vision signals (advisory)
  - Present summary to user
  - Shut down team
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

---

## Anti-Patterns

1. **Do not implement stories yourself.** The main session coordinates -- it does not implement. Spawn an implementer for every story, even if the work seems trivial. The coordinator must not also be an implementer.
2. **Do not summarize context blocks.** Always send the full story file text and full Technical Notes verbatim. Summarizing loses acceptance criteria, file paths, and constraints that implementers need.
3. **Do not mark stories DONE without verifying acceptance criteria.** Every AC must be confirmed met before the story status changes.
4. **Do not proceed to closure with unverified stories.** If any AC is unmet, send the implementer back. Do not close the epic with partial completion.
5. **Do not skip the documentation assessment.** The epic cannot be archived until the documentation impact is evaluated per `.claude/rules/documentation.md`.
6. **Do not commit automatically.** The closure sequence offers to commit -- the user must explicitly approve.
7. **Do not spawn a PM teammate.** The main session coordinates directly. There is no PM role during dispatch.
8. **Do not skip the context-layer assessment.** The epic cannot be archived until the context-layer impact is evaluated per `.claude/rules/context-layer-assessment.md`.
9. **Do not mark stories DONE without code-reviewer approval** (except context-layer-only stories) unless the user explicitly overrides via the circuit breaker escalation. The reviewer is the quality gate -- the main session does not bypass it by verifying ACs directly.
10. **Do not relay SHOULD FIX findings to implementers.** The fix loop is exclusively for MUST FIX items. Record SHOULD FIX in epic History during closure.
11. **Do not spawn context-layer stories with worktree isolation.** Context-layer files (CLAUDE.md, `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, etc.) are shared infrastructure. Stories modifying only these files must run in the main checkout without `isolation: "worktree"`.
