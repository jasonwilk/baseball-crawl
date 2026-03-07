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

### Step 2: Spawn implementing agents

Spawn each implementing agent with the following context:

```
You are a [agent-type] agent on the [team-name] team. Wait for the main session to assign you a story via SendMessage. Do not begin work until you receive your story assignment with the full story file text and Technical Notes.
```

If this is a multi-wave epic, spawn only wave-1 agents now. Later-wave agents are spawned during Phase 3 as dependencies complete.

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
2. **Check context-layer routing.** Scan the story's "Files to Create or Modify" section. If any file matches a context-layer path (see Routing Precedence in `/.claude/rules/dispatch-pattern.md`), that story MUST go to `claude-architect` regardless of the Agent Hint.
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

Satisfy all acceptance criteria and report back when complete. Do NOT update story status files -- the main session handles all status updates.
```

**Context block requirements** (per `/.claude/rules/dispatch-pattern.md`):
- Include the **full story file text** verbatim. Never summarize.
- Include the **full epic Technical Notes** verbatim.
- When a story has completed upstream dependencies with Handoff Context declarations, include the declared artifact paths and descriptions.

Assign stories in parallel when they have no file conflicts.

### Step 5: Monitor and verify

Stay active in the team. As each implementer reports completion:

1. **Verify all acceptance criteria** for the reported story. Read the story file to confirm each criterion is satisfied.
2. **If criteria are met**: Mark the story `DONE` in both the story file and epic Stories table.
3. **If criteria are not met**: Send the implementer back with specific feedback identifying which criteria failed and why. Do not proceed to marking DONE.

### Step 6: Cascade

After marking a story DONE, check for newly unblocked stories (stories whose blocking dependencies are now all DONE).

- If the required agent type is already on the team, assign the story directly (repeat from Step 2).
- If a new agent type is needed, spawn the agent and assign the story.
- If no more stories are eligible and some are still in progress, wait for more completions.
- If all stories are DONE, proceed to Phase 4 (or Phase 5 if no review chain).

---

## Phase 4: Optional Review Chain

If the user specified the "and review" modifier (e.g., "implement E-NNN and review"):

- After all stories are verified DONE, chain into the review-epic workflow at `.claude/skills/review-epic/SKILL.md`.
- Run the review before proceeding to the closure sequence (Phase 5).
- The main session invokes the review skill directly.

If the modifier was not specified, skip this phase and proceed directly to Phase 5.

---

## Phase 5: Closure Sequence

When all stories are verified DONE (and the optional review chain is complete), execute the following closure sequence in order.

**Before spinning down the team:**

### Step 1: Validate all work

For every story in the epic, confirm all acceptance criteria are met. This is a final check -- if any are unmet, send the implementer back with specific feedback. Do not proceed to closure until every story is verified DONE.

### Step 2: Update the epic completely

- Confirm all story file statuses are DONE.
- Epic Stories table reflects current reality (all rows DONE).
- Epic status updated to COMPLETED.
- History entry added with the completion date and a summary of what was accomplished.
- Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information (credentials, tokens, secrets) OUT of epic files.

### Step 3: Documentation assessment

Review the epic's scope against the update triggers in `.claude/rules/documentation.md`. If any trigger fires, spawn docs-writer (if not already on the team) to update affected docs before archiving. If no trigger fires, record "No documentation impact" in the epic's History section. The epic MUST NOT be archived until this assessment is complete and any required doc updates are done.

### Step 4: Archive the epic

Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`. Instruct an implementing agent still on the team to perform this move. Do not proceed to team shutdown until the archive is confirmed.

### Step 5: Update PM memory

Move the epic from "Active Epics" to "Archived Epics" in the PM's MEMORY.md (`.claude/agent-memory/product-manager/MEMORY.md`). Note any follow-up work or newly unblocked items.

### Step 6: Review ideas backlog

Check `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

### Step 7: Present a summary to the user

Before ending the dispatch, present a clear summary including:
- Epic ID and title
- List of stories completed (with brief descriptions)
- Key artifacts created or modified
- Any follow-up work identified
- Any ideas that may now be promotable

### Step 8: Shut down all teammates

Send a `shutdown_request` to each implementing agent on the team. Wait for shutdown confirmations. Delete the team.

**After spinning down the team:**

### Step 9: Offer to scan and commit

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
Phase 1: Read epic's Dispatch Team section
  - Extract implementer types (no PM)
  - Plan multi-wave spawning if dependencies exist
  |
  v
Phase 2: Create team, spawn implementers directly
  - Set epic to ACTIVE if currently READY
  |
  v
Phase 3: Coordination loop
  - Identify eligible stories (TODO + deps satisfied)
  - Route to agent type (Agent Hint > context-layer check > routing table)
  - Mark stories IN_PROGRESS, assign with full context blocks
  - Monitor completion, verify ACs, send back if unmet
  - Mark verified stories DONE, cascade to newly unblocked stories
  - Spawn later-wave agents as dependencies complete
  |
  v
[If "and review": Phase 4 -- chain into review-epic skill]
  |
  v
Phase 5: Closure sequence
  - Validate all work (final AC check)
  - Update epic to COMPLETED with history entry
  - Documentation assessment (spawn docs-writer if needed)
  - Archive epic to /.project/archive/
  - Update PM memory
  - Review ideas backlog
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
If the review chain runs but there are no uncommitted changes to review, the review-epic skill handles this gracefully. No special handling needed here.

---

## Anti-Patterns

1. **Do not implement stories yourself.** The main session coordinates -- it does not implement. Spawn an implementer for every story, even if the work seems trivial. The coordinator must not also be an implementer.
2. **Do not summarize context blocks.** Always send the full story file text and full Technical Notes verbatim. Summarizing loses acceptance criteria, file paths, and constraints that implementers need.
3. **Do not mark stories DONE without verifying acceptance criteria.** Every AC must be confirmed met before the story status changes.
4. **Do not proceed to closure with unverified stories.** If any AC is unmet, send the implementer back. Do not close the epic with partial completion.
5. **Do not skip the documentation assessment.** The epic cannot be archived until the documentation impact is evaluated per `.claude/rules/documentation.md`.
6. **Do not commit automatically.** The closure sequence offers to commit -- the user must explicitly approve.
7. **Do not spawn a PM teammate.** The main session coordinates directly. There is no PM role during dispatch.
