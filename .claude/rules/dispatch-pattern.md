---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

## CRITICAL: Team Lead Dispatch Boundary

**The team lead (user-facing agent) MUST NOT act as dispatch coordinator.** When the user requests epic or story execution, the team lead's only job is:

1. **Spawn the product-manager (PM) as a teammate.**
2. **Relay the user's request to the PM verbatim.**
3. **Step back and let the PM coordinate.**

The team lead MUST NOT:
- Create dispatch teams or spawn implementing agents directly
- Mark story statuses (`IN_PROGRESS`, `DONE`, etc.)
- Update epic tables or story files
- Verify acceptance criteria
- Make routing decisions about which agent handles which story

All of these are the PM's responsibilities. If the team lead performs any of them, it is a routing violation -- even if the end result is correct. The PM exists precisely to own this coordination, and bypassing it creates state management gaps and accountability confusion.

**If the PM is unavailable or spawn fails**, follow the Dispatch Failure Protocol in `workflow-discipline.md`: report to the user and ask how to proceed. Do not improvise.

## How Dispatch Works

This project uses **Agent Teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) for dispatching stories. Teams let any agent spawn teammates, who can in turn spawn other teammates -- no nesting limits.

## Team Composition

Every dispatch team has two kinds of members:

1. **PM (coordinator)** -- Always present. The PM joins every dispatch team as a standing member. The PM does not implement; it manages state, verifies acceptance criteria, and coordinates the team throughout the epic's execution.

2. **Specialist agents (implementers)** -- Spawned by the PM for specific stories. These do the actual work: writing code, designing schemas, configuring agents, etc.

The PM does not create the team and walk away. The PM stays active in the team for the duration of the dispatch, managing the lifecycle of every story.

## PM Responsibilities During Dispatch

The PM handles all state management and coordination while the team is active:

- **Status updates**: Mark stories `IN_PROGRESS` before dispatching, `DONE` after verifying. Update both story files and the epic Stories table atomically.
- **Acceptance criteria verification**: Before marking any story `DONE`, verify that all acceptance criteria are met. If criteria are not met, send the implementer back with specific feedback.
- **Dependency management**: When a story completes, check whether any `BLOCKED` stories are now unblocked. If so, update their status and dispatch them.
- **Epic table sync**: Keep the epic's Stories table in sync with individual story file statuses at all times.
- **History entries**: Record what happened in the epic file -- when stories started, completed, and any notable decisions made during execution.
- **Team shutdown**: When all stories are `DONE` (or the dispatch is halted), execute the Closure Sequence (see "The Dispatch Flow") before shutting down implementing agents and deleting the team.

## Specialist Agent Responsibilities During Dispatch

Implementing agents focus on their assigned story:

- Read the story file and epic Technical Notes provided in the context block.
- Satisfy all acceptance criteria.
- Report completion back to the PM (the PM verifies and updates status).

Implementing agents do NOT update story statuses or epic tables. That is the PM's job.

## The Dispatch Flow

1. User requests dispatch ("start epic X", "execute story X", "dispatch stories"). Dispatch MUST be initiated by an explicit user request. The PM MUST NOT self-initiate dispatch after completing epic formation -- "define the epic" and "execute the epic" are separate user actions. Compound requests that explicitly include dispatch language (e.g., "define and execute," "plan and dispatch," "create the epic and start it") authorize both planning and dispatch in sequence.
2. PM reads the epic, identifies eligible stories (TODO with satisfied dependencies).
3. PM marks eligible stories `IN_PROGRESS` in both story files and epic table.
4. PM creates a team (`TeamCreate`) and spawns implementing agents as teammates.
5. Implementing agents work on their assigned stories.
6. As each implementer reports completion, PM verifies acceptance criteria.
7. PM marks verified stories `DONE` in both story files and epic table.
8. PM checks for newly unblocked stories and dispatches them (repeat from step 2).

### Closure Sequence (replaces the former single final step)

When all stories are verified DONE, the PM executes the following closure sequence in order.

**Before spinning down the team:**

9. **Validate all work.** For every story in the epic, confirm all acceptance criteria are met. If any are unmet, send the implementer back with specific feedback -- do not proceed to closure.

10. **Update the epic completely.**
    - Confirm all story file statuses are DONE.
    - Epic Stories table reflects current reality (all rows DONE).
    - Epic status updated to COMPLETED.
    - History entry added with the completion date and a summary of what was accomplished.
    - Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information (credentials, tokens, secrets) OUT of epic files.

11. **Documentation assessment.** Review the epic's scope against the update triggers in `.claude/rules/documentation.md`. If any trigger fires, dispatch docs-writer to update affected docs before archiving. If no trigger fires, record "No documentation impact" in the epic's History section. The epic MUST NOT be archived until this assessment is complete and any required doc updates are done.

12. **Archive the epic.** Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`. The PM has no Bash tool, so the PM must request this move from an implementing agent still on the team before shutting them down.

13. **Update PM memory.** Move the epic from "Active Epics" to "Archived Epics" in MEMORY.md. Note any follow-up work or newly unblocked items.

14. **Review ideas backlog.** Check `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

15. **Present a summary to the user.** Before ending the dispatch, present a clear summary including:
    - Epic ID and title
    - List of stories completed (with brief descriptions)
    - Key artifacts created or modified
    - Any follow-up work identified
    - Any ideas that may now be promotable

**After spinning down the team:**

16. **Offer to scan and commit.** After shutting down teammates and deleting the team, offer to run the PII scan and commit the changes. Commit must NOT happen automatically -- the user must explicitly approve before any commit happens.

## Agent Selection for Dispatch

| Story Domain | Agent Type |
|-------------|-----------|
| Python implementation, crawlers, parsers, tests | `general-purpose` (software-engineer role in prompt) |
| Database schema, SQL migrations, ETL | `general-purpose` (data-engineer role in prompt) |
| API exploration, endpoint docs | `general-purpose` (api-scout role in prompt) |
| Context-layer files: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/**` | `claude-architect` |
| Documentation (`docs/admin/`, `docs/coaching/`) | `docs-writer` |
| UI/UX design: wireframes, layout specs, component inventories, user flows | `ux-designer` |

**Dispatch Team metadata**: Epics may include a `## Dispatch Team` section (between Stories and Technical Notes) that explicitly lists the agents needed for the epic. When this section is present and non-empty, the PM should prefer it over inferring agents from story domains using the table above. When the section is absent or empty, the PM falls back to the routing table. The PM always retains final routing authority -- the Dispatch Team section is advisory.

**Routing Precedence**: If a story's "Files to Create or Modify" includes any context-layer path listed above, route to `claude-architect` regardless of the story's primary domain. The only exception is the PM updating its own memory files (`.claude/agent-memory/product-manager/`) during normal status-update work.

## Task Tool vs. Agent Teams

- **Task tool**: Single subagent, no further nesting. Use for simple consultations (e.g., PM consulting baseball-coach for domain input).
- **Agent Teams**: Multi-agent coordination with free spawning. Use for epic/story dispatch where the PM needs to coordinate multiple implementing agents over time.

The PM chooses the appropriate mechanism based on the task. Consultation = Task tool. Dispatch = Agent Teams.

## Context Packaging

Every teammate dispatch MUST include the full story file text and full epic Technical Notes. Never summarize -- implementing agents need every acceptance criterion, file path, and constraint verbatim.
