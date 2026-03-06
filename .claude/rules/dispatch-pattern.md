---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

## CRITICAL: Team Lead Spawning Responsibility

**The team lead (user-facing agent) is the ONLY agent that can create teams and spawn teammates.** This is a hard constraint of the Agent Teams architecture -- teammates cannot spawn other teammates.

When the user requests epic or story execution, the team lead:

1. **Reads the epic** to determine team composition (from the Dispatch Team section or the routing table).
2. **Creates the team** via `TeamCreate`.
3. **Spawns PM + all implementing agents** listed in the epic's Dispatch Team section. Each agent is spawned with appropriate context (see Context Packaging below).
4. **Remains available for spawn requests.** If PM identifies newly unblocked stories requiring an agent type not yet on the team, PM messages the team lead to spawn the additional agent. The team lead fulfills these requests promptly.

The team lead MUST NOT:
- Assign stories to implementers (PM does this via messaging)
- Mark story statuses (`IN_PROGRESS`, `DONE`, etc.)
- Update epic tables or story files
- Verify acceptance criteria
- Make routing decisions about which agent handles which story

These are PM's coordination responsibilities. The team lead's role is spawning and availability -- not coordination.

**If PM or an implementer spawn fails**, follow the Dispatch Failure Protocol in `workflow-discipline.md`: report to the user and ask how to proceed. Do not improvise.

## How Dispatch Works

This project uses **Agent Teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) for dispatching stories. Only the team lead can create teams (`TeamCreate`) and spawn teammates (`Agent` tool). Teammates communicate with each other and the team lead via `SendMessage` but cannot add new members to the team.

## Team Composition

Every dispatch team has three roles:

1. **Team lead (spawner)** -- The user-facing agent. Creates the team, spawns all members, and remains available for additional spawn requests throughout the dispatch. Does not coordinate stories or verify work.

2. **PM (coordinator)** -- Always present. Spawned by the team lead alongside implementers. The PM does not implement; it assigns stories via messaging, verifies acceptance criteria, manages status updates, and coordinates the team throughout the epic's execution.

3. **Specialist agents (implementers)** -- Spawned by the team lead based on the epic's Dispatch Team section (or the routing table). These do the actual work: writing code, designing schemas, configuring agents, etc. PM assigns their stories via `SendMessage`.

### Spawning Scenarios

**At team creation**: The team lead reads the epic's Dispatch Team section and spawns PM + all listed implementers in one batch. If no Dispatch Team section exists, the team lead spawns PM only and tells PM: "No Dispatch Team section found. Determine required agents and message me to spawn them."

**Mid-dispatch (cascading)**: When PM identifies newly unblocked stories that need an agent type not already on the team, PM messages the team lead: "Please spawn [agent-type] for story E-NNN-SS." The team lead spawns the agent and notifies PM.

## PM Responsibilities During Dispatch

The PM handles all state management and coordination while the team is active:

- **Story assignment**: Assign stories to implementers via `SendMessage`, providing the full story file text and epic Technical Notes.
- **Status updates**: Mark stories `IN_PROGRESS` before assigning, `DONE` after verifying. Update both story files and the epic Stories table atomically.
- **Acceptance criteria verification**: Before marking any story `DONE`, verify that all acceptance criteria are met. If criteria are not met, send the implementer back with specific feedback.
- **Dependency management**: When a story completes, check whether any `BLOCKED` stories are now unblocked. If so, update their status and assign them to teammates -- or request the team lead to spawn additional agents if needed.
- **Epic table sync**: Keep the epic's Stories table in sync with individual story file statuses at all times.
- **History entries**: Record what happened in the epic file -- when stories started, completed, and any notable decisions made during execution.
- **Team shutdown**: When all stories are `DONE` (or the dispatch is halted), execute the Closure Sequence (see below) before requesting the team lead to shut down teammates.

PM coordinates entirely via `SendMessage`. PM never uses `TeamCreate` or the `Agent` tool.

## Specialist Agent Responsibilities During Dispatch

Implementing agents focus on their assigned story:

- Read the story file and epic Technical Notes provided in the context block.
- Satisfy all acceptance criteria.
- Report completion back to the PM via `SendMessage` (the PM verifies and updates status).

Implementing agents do NOT update story statuses or epic tables. That is the PM's job.

## The Dispatch Flow

1. User requests dispatch ("start epic X", "execute story X", "dispatch stories"). Dispatch MUST be initiated by an explicit user request. The PM MUST NOT self-initiate dispatch after completing epic formation -- "define the epic" and "execute the epic" are separate user actions. Compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch," "create the epic and start it") authorize both planning and dispatch in sequence.
2. Team lead reads the epic, identifies the Dispatch Team section (or falls back to the routing table).
3. Team lead creates the team (`TeamCreate`) and spawns PM + all implementing agents.
4. Team lead messages PM with the epic context and a roster of spawned teammates.
5. PM reads the epic, identifies eligible stories (TODO with satisfied dependencies), and marks them `IN_PROGRESS`.
6. PM assigns stories to implementers via `SendMessage`, providing full story text and Technical Notes.
7. Implementing agents work on their assigned stories and report completion to PM.
8. As each implementer reports completion, PM verifies acceptance criteria.
9. PM marks verified stories `DONE` in both story files and epic table.
10. PM checks for newly unblocked stories. If the required agent is on the team, PM assigns directly. If a new agent type is needed, PM messages the team lead to spawn it (repeat from step 6).

### Closure Sequence

When all stories are verified DONE, the PM executes the following closure sequence in order.

**Before spinning down the team:**

11. **Validate all work.** For every story in the epic, confirm all acceptance criteria are met. If any are unmet, send the implementer back with specific feedback -- do not proceed to closure.

12. **Update the epic completely.**
    - Confirm all story file statuses are DONE.
    - Epic Stories table reflects current reality (all rows DONE).
    - Epic status updated to COMPLETED.
    - History entry added with the completion date and a summary of what was accomplished.
    - Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information (credentials, tokens, secrets) OUT of epic files.

13. **Documentation assessment.** Review the epic's scope against the update triggers in `.claude/rules/documentation.md`. If any trigger fires, request the team lead to spawn docs-writer (if not already on the team) to update affected docs before archiving. If no trigger fires, record "No documentation impact" in the epic's History section. The epic MUST NOT be archived until this assessment is complete and any required doc updates are done.

14. **Archive the epic.** Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`. PM instructs an implementer still on the team to perform this move.

15. **Update PM memory.** Move the epic from "Active Epics" to "Archived Epics" in MEMORY.md. Note any follow-up work or newly unblocked items.

16. **Review ideas backlog.** Check `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

17. **Present a summary to the user.** Before ending the dispatch, present a clear summary including:
    - Epic ID and title
    - List of stories completed (with brief descriptions)
    - Key artifacts created or modified
    - Any follow-up work identified
    - Any ideas that may now be promotable

**After spinning down the team:**

18. **Offer to scan and commit.** After the team lead shuts down teammates and deletes the team, the team lead offers to run the PII scan and commit the changes. Commit must NOT happen automatically -- the user must explicitly approve before any commit happens.

## Agent Selection for Dispatch

| Story Domain | Agent Type |
|-------------|-----------|
| Python implementation, crawlers, parsers, tests | `general-purpose` (software-engineer role in prompt) |
| Database schema, SQL migrations, ETL | `general-purpose` (data-engineer role in prompt) |
| API exploration, endpoint docs | `general-purpose` (api-scout role in prompt) |
| Context-layer files: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/**` | `claude-architect` |
| Documentation (`docs/admin/`, `docs/coaching/`) | `docs-writer` |
| UI/UX design: wireframes, layout specs, component inventories, user flows | `ux-designer` |

**Dispatch Team metadata**: Epics may include a `## Dispatch Team` section (between Stories and Technical Notes) that explicitly lists the agents needed for the epic. When this section is present and non-empty, the team lead should prefer it over inferring agents from story domains using the table above. When the section is absent or empty, the team lead spawns PM only and PM determines required agents via the routing table, messaging the team lead to spawn them. The PM always retains final routing authority -- the Dispatch Team section is advisory.

**Routing Precedence**: If a story's "Files to Create or Modify" includes any context-layer path listed above, route to `claude-architect` regardless of the story's primary domain. The only exception is the PM updating its own memory files (`.claude/agent-memory/product-manager/`) during normal status-update work.

## Task Tool vs. Agent Teams

- **Task tool**: Single subagent, no further nesting. Use for simple consultations (e.g., PM consulting baseball-coach for domain input).
- **Agent Teams**: Multi-agent coordination for epic/story dispatch. The team lead creates the team and spawns all agents; PM coordinates via messaging.

The PM chooses the appropriate mechanism based on the task. Consultation = Task tool. Dispatch = Agent Teams (team lead spawns, PM coordinates).

## Context Packaging

Every teammate dispatch MUST include the full story file text and full epic Technical Notes. Never summarize -- implementing agents need every acceptance criterion, file path, and constraint verbatim.
