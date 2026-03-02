---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

## How Dispatch Works

This project uses **Agent Teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) for dispatching stories. Teams let any agent spawn teammates, who can in turn spawn other teammates -- no nesting limits.

## The Dispatch Flow

1. User requests dispatch ("start epic X", "execute story X", "dispatch stories")
2. Orchestrator routes to PM (via Task tool or direct invocation)
3. PM reads the epic, identifies eligible stories
4. PM creates a team (`TeamCreate`), spawns implementing agents as teammates (`Agent` tool with `team_name`)
5. Implementing agents work on their assigned stories
6. PM verifies acceptance criteria, marks stories DONE
7. PM shuts down teammates and deletes the team when done

## Agent Selection for Dispatch

| Story Domain | Agent Type |
|-------------|-----------|
| Python implementation, crawlers, parsers, tests | `general-purpose` |
| Database schema, SQL migrations, ETL | `general-purpose` (data-engineer role in prompt) |
| API exploration, endpoint docs | `general-purpose` (api-scout role in prompt) |
| Agent config, CLAUDE.md, rules, skills | `claude-architect` |

## Task Tool vs. Agent Teams

- **Task tool**: Single subagent, no further nesting. Use for simple consultations (e.g., PM consulting baseball-coach for domain input).
- **Agent Teams**: Multi-agent coordination with free spawning. Use for epic/story dispatch where the PM needs to spawn multiple implementing agents.

The PM chooses the appropriate mechanism based on the task. Consultation = Task tool. Dispatch = Agent Teams.

## Context Packaging

Every teammate dispatch MUST include the full story file text and full epic Technical Notes. Never summarize -- implementing agents need every acceptance criterion, file path, and constraint verbatim.
