---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

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
- **Team shutdown**: When all stories are `DONE` (or the dispatch is halted), shut down implementing agents and delete the team.

## Specialist Agent Responsibilities During Dispatch

Implementing agents focus on their assigned story:

- Read the story file and epic Technical Notes provided in the context block.
- Satisfy all acceptance criteria.
- Report completion back to the PM (the PM verifies and updates status).

Implementing agents do NOT update story statuses or epic tables. That is the PM's job.

## The Dispatch Flow

1. User requests dispatch ("start epic X", "execute story X", "dispatch stories").
2. Orchestrator routes to PM.
3. PM reads the epic, identifies eligible stories (TODO with satisfied dependencies).
4. PM marks eligible stories `IN_PROGRESS` in both story files and epic table.
5. PM creates a team (`TeamCreate`) and spawns implementing agents as teammates.
6. Implementing agents work on their assigned stories.
7. As each implementer reports completion, PM verifies acceptance criteria.
8. PM marks verified stories `DONE` in both story files and epic table.
9. PM checks for newly unblocked stories and dispatches them (repeat from step 3).
10. When all stories are done, PM marks the epic `COMPLETED`, shuts down teammates, and deletes the team.

## Agent Selection for Dispatch

| Story Domain | Agent Type |
|-------------|-----------|
| Python implementation, crawlers, parsers, tests | `general-purpose` |
| Database schema, SQL migrations, ETL | `general-purpose` (data-engineer role in prompt) |
| API exploration, endpoint docs | `general-purpose` (api-scout role in prompt) |
| Context-layer files: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/**` | `claude-architect` |

**Routing Precedence**: If a story's "Files to Create or Modify" includes any context-layer path listed above, route to `claude-architect` regardless of the story's primary domain. The only exception is the PM updating its own memory files (`.claude/agent-memory/product-manager/`) during normal status-update work.

## Task Tool vs. Agent Teams

- **Task tool**: Single subagent, no further nesting. Use for simple consultations (e.g., PM consulting baseball-coach for domain input).
- **Agent Teams**: Multi-agent coordination with free spawning. Use for epic/story dispatch where the PM needs to coordinate multiple implementing agents over time.

The PM chooses the appropriate mechanism based on the task. Consultation = Task tool. Dispatch = Agent Teams.

## Context Packaging

Every teammate dispatch MUST include the full story file text and full epic Technical Notes. Never summarize -- implementing agents need every acceptance criterion, file path, and constraint verbatim.
