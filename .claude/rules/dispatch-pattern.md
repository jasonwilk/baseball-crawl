---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

## Main Session Dispatch Responsibility

**The main session (user-facing agent) acts as both spawner and coordinator during dispatch.** It creates teams, spawns implementers and the code-reviewer, assigns stories, routes completed work through the review loop, manages statuses, and runs the closure sequence. There is no separate PM teammate during dispatch.

When the user requests epic or story execution, the main session:

1. **Reads the epic** to determine team composition (from the Dispatch Team section or the routing table).
2. **Creates the team** via `TeamCreate` and spawns all implementing agents listed in the epic's Dispatch Team section, plus the code-reviewer (spawned automatically).
3. **Assigns stories** directly to implementers with full context blocks (story file text + Technical Notes).
4. **Monitors completion**, routes code stories through the code-reviewer, manages statuses, and cascades to newly unblocked stories.

**If an implementer spawn fails**, follow the Dispatch Failure Protocol in `workflow-discipline.md`: report to the user and ask how to proceed. Do not improvise.

## How Dispatch Works

This project uses **Agent Teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) for dispatching stories. The main session creates teams (`TeamCreate`) and spawns implementers (`Agent` tool). Implementers communicate with the main session via `SendMessage` but cannot add new members to the team.

## Team Composition

Every dispatch team has three roles:

1. **Main session (spawner + coordinator)** -- The user-facing agent. Creates the team, spawns implementers and the code-reviewer, assigns stories with full context blocks, routes completed work to the reviewer, manages all status updates, and runs the closure sequence.

2. **Specialist agents (implementers)** -- Spawned by the main session based on the epic's Dispatch Team section (or the routing table). These do the actual work: writing code, designing schemas, configuring agents, etc. The main session assigns their stories directly.

3. **Code-reviewer (quality gate)** -- Persistent per-epic, spawned automatically by the implement skill alongside implementers. Reviews every code story before it can be marked DONE. Not listed in the epic's Dispatch Team section -- it is infrastructure. See `.claude/agents/code-reviewer.md` for the agent definition.

### Spawning Scenarios

**At team creation**: The main session reads the epic's Dispatch Team section and spawns all listed implementers. If no Dispatch Team section exists, the main session uses the Agent Selection routing table to determine which agent types are needed based on story domains, and spawns them.

**Multi-wave epics**: The main session reviews the full dependency graph at dispatch start. It spawns wave-1 agents immediately, then spawns later-wave agents directly as their dependencies complete. For single-wave epics (no inter-story dependencies), all agents are spawned at once.

**Mid-dispatch (cascading)**: A fallback for truly unexpected agent needs discovered mid-dispatch -- when a story reveals a requirement that was not anticipated during planning. The main session spawns the additional agent type directly and assigns the story.

## Implementing Agent Responsibilities During Dispatch

Implementing agents focus on their assigned story:

- Read the story file and epic Technical Notes provided in the context block.
- Satisfy all acceptance criteria.
- Report completion back to the main session via `SendMessage`.

Implementing agents do NOT update story statuses or epic tables. That is the main session's job.

## The Dispatch Flow

1. User requests dispatch ("start epic X", "execute story X", "dispatch stories"). Dispatch MUST be initiated by an explicit user request. Dispatch MUST NOT self-initiate after completing epic formation -- "define the epic" and "execute the epic" are separate user actions. Compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch," "create the epic and start it") authorize both planning and dispatch in sequence.
2. Main session reads the epic, identifies the Dispatch Team section (or falls back to the routing table).
3. Main session creates the team (`TeamCreate`) and spawns all implementing agents.
4. Main session identifies eligible stories (TODO with satisfied dependencies), marks them `IN_PROGRESS`, and assigns them to implementers with full context blocks (story file text + Technical Notes).
5. Implementing agents work on their assigned stories and report completion (with `## Files Changed`) to the main session.
6. As each implementer reports completion, the main session checks the context-layer-only skip condition: if the story modifies ONLY context-layer files and no Python code, the main session verifies ACs directly and marks DONE. Otherwise, the main session routes the work to the code-reviewer.
7. The code-reviewer examines the implementation and returns APPROVED or NOT APPROVED with structured findings. If APPROVED, the main session marks the story DONE. If NOT APPROVED (MUST FIX findings), the main session routes MUST FIX items to the implementer for fixes. After fixes, the reviewer re-reviews (max 2 rounds). If the 2nd review still has MUST FIX findings, the main session escalates to the user.
8. Main session marks reviewer-approved stories `DONE` in both story files and epic table.
9. Main session checks for newly unblocked stories. If the required agent is on the team, it assigns directly. If a new agent type is needed, it spawns the agent and assigns the story (repeat from step 5).

### Closure Sequence

When all stories are verified DONE, the main session executes the following closure sequence in order.

**Before spinning down the team:**

9. **Validate all work.** Confirm all stories are DONE. Per-story validation was performed by the code-reviewer during the dispatch loop (for code stories) or by the main session directly (for context-layer-only stories). This step confirms completion status, not a re-review of all code.

10. **Update the epic completely.**
    - Confirm all story file statuses are DONE.
    - Epic Stories table reflects current reality (all rows DONE).
    - Epic status updated to COMPLETED.
    - History entry added with the completion date and a summary of what was accomplished.
    - Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information (credentials, tokens, secrets) OUT of epic files.

11. **Documentation assessment.** Review the epic's scope against the update triggers in `.claude/rules/documentation.md`. If any trigger fires, spawn docs-writer (if not already on the team) to update affected docs before archiving. If no trigger fires, record "No documentation impact" in the epic's History section. The epic MUST NOT be archived until this assessment is complete and any required doc updates are done.

12. **Context-layer assessment.** Evaluate the epic's impact on the context layer per `.claude/rules/context-layer-assessment.md`. Assess each of the six triggers with an explicit yes/no verdict and record all verdicts in the epic's History section. If any trigger fires, spawn claude-architect (if not already on the team) to codify the findings before archiving. The epic MUST NOT be archived until this assessment is complete and any required codification is done.

13. **Archive the epic.** Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`. The main session instructs an implementer still on the team to perform this move.

14. **Update PM memory.** Move the epic from "Active Epics" to "Archived Epics" in the PM's MEMORY.md. Note any follow-up work or newly unblocked items.

15. **Review ideas backlog.** Check `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

16. **Present a summary to the user.** Before ending the dispatch, present a clear summary including:
    - Epic ID and title
    - List of stories completed (with brief descriptions)
    - Key artifacts created or modified
    - Any follow-up work identified
    - Any ideas that may now be promotable

### Team Teardown

17. **Shut down all teammates.** Send a `shutdown_request` to each implementing agent on the team. Wait for shutdown confirmations. Delete the team.

**After spinning down the team:**

18. **Offer to scan and commit.** After shutting down teammates and deleting the team, the main session offers to run the PII scan and commit the changes. Commit must NOT happen automatically -- the user must explicitly approve before any commit happens.

## Agent Selection for Dispatch

| Story Domain | Agent Type |
|-------------|-----------|
| Python implementation, crawlers, parsers, tests | `general-purpose` (software-engineer role in prompt) |
| Database schema, SQL migrations, ETL | `general-purpose` (data-engineer role in prompt) |
| API exploration, endpoint docs | `general-purpose` (api-scout role in prompt) |
| Context-layer files: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/**` | `claude-architect` |
| Documentation (`docs/admin/`, `docs/coaching/`) | `docs-writer` |
| UI/UX design: wireframes, layout specs, component inventories, user flows | `ux-designer` |
| Code review (automatic -- not routed by story domain) | `code-reviewer` (spawned automatically by the implement skill for every dispatch; not assigned stories) |

**Dispatch Team metadata**: Epics may include a `## Dispatch Team` section (between Stories and Technical Notes) that explicitly lists the agents needed for the epic. When this section is present and non-empty, the main session should prefer it over inferring agents from story domains using the table above. When the section is absent or empty, the main session determines required agents from the routing table. The main session retains final routing authority -- the Dispatch Team section is advisory.

**Agent Hint**: Stories may carry an optional `## Agent Hint` field that declares which agent type should implement the story. When an Agent Hint is present, the main session should prefer it over file-path inference from the routing table above. The hint is advisory -- the main session may override it based on team composition, agent availability, or other factors.

**Routing Precedence**: If a story's "Files to Create or Modify" includes any context-layer path listed above, route to `claude-architect` regardless of the story's primary domain or Agent Hint value. The only exception is the main session updating PM memory files (`.claude/agent-memory/product-manager/`) during normal closure work.

## Task Tool vs. Agent Teams

- **Task tool**: Single subagent, no further nesting. Use for simple consultations (e.g., consulting baseball-coach for domain input during epic formation).
- **Agent Teams**: Multi-agent coordination for epic/story dispatch. The main session creates the team, spawns implementers, and coordinates directly.

The main session chooses the appropriate mechanism based on the task. Consultation = Task tool. Dispatch = Agent Teams.

## Context Packaging

Every implementer dispatch MUST include the full story file text and full epic Technical Notes. Never summarize -- implementing agents need every acceptance criterion, file path, and constraint verbatim.

When assigning a story that has completed upstream dependencies, the main session should check the upstream stories for Handoff Context declarations. If any upstream story declares artifacts produced for the current story, the main session includes those declared artifacts (file paths and descriptions) in the context block alongside the full story file and Technical Notes.
