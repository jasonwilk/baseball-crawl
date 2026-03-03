# Agent Guide

## Overview

Baseball-crawl uses an ecosystem of AI agents (powered by Claude Code) to manage development. Each agent has a specific role -- product management, coding, API exploration, domain expertise, documentation, or infrastructure -- and they collaborate through a structured epic/story workflow.

The agent ecosystem exists because the project is primarily developed through AI-assisted workflows. Rather than a single general-purpose AI, the work is split across specialized agents with focused prompts, appropriate tool access, and clear responsibilities. This keeps context windows manageable and output quality high.

Agent definitions live in `.claude/agents/`. Rules governing their behavior live in `.claude/rules/`. Memory files that persist across sessions live in `.claude/agent-memory/`.

## Agents

| Agent | Model | Role |
|-------|-------|------|
| **product-manager** | Opus | Owns what to build, why, and in what order. Creates epics and stories, prioritizes the backlog, dispatches implementation work, and closes completed work. Never writes code. |
| **claude-architect** | Opus | Designs and manages agents, `CLAUDE.md`, rules, skills, and hooks. Maintains the agent ecosystem itself. |
| **baseball-coach** | Sonnet | Domain expert. Translates coaching needs into technical requirements, validates schemas against real coaching use cases, and defines what statistics matter. |
| **api-scout** | Sonnet | Explores the GameChanger API, documents endpoints in `docs/gamechanger-api.md`, and guides credential rotation. |
| **data-engineer** | Sonnet | Designs database schemas, SQL migrations, and ETL pipelines. Informs the data layer from both domain requirements and API discoveries. |
| **general-dev** | Sonnet | Implements Python code: crawlers, parsers, loaders, tests, utilities. Works from specifications produced by other agents. |
| **docs-writer** | Sonnet | Writes and maintains human-readable documentation for admin/developer and coaching staff audiences. |

## How to Work with Agents

### The Product Manager as Entry Point

For most work, start by talking to the **product-manager**. The PM is the coordinator:

- Tell the PM what you want built, fixed, or investigated.
- The PM discovers requirements, writes epics and stories with acceptance criteria, and dispatches work to specialist agents.
- The PM manages story statuses and verifies acceptance criteria when work is complete.

**Example**: "I want a scouting report that shows the opposing pitcher's K/9 and BB/9 splits." The PM would consult the baseball-coach for requirements, check with data-engineer on schema readiness, and write stories for general-dev to implement.

### Direct-Routing Exceptions

Three agents can be invoked directly without going through the PM:

- **api-scout**: For exploratory API work, endpoint discovery, or credential troubleshooting.
- **baseball-coach**: For domain questions about baseball analytics, stat definitions, or coaching needs.
- **claude-architect**: For changes to agent definitions, `CLAUDE.md`, rules, skills, or hooks.

### Invoking an Agent

In Claude Code, agents are invoked using the agent prompt system. For example:

```
@product-manager I need a way to compare our batting lineup against the opponent's pitching stats.
```

Or for direct-routing exceptions:

```
@baseball-coach What stats should we track for a starting pitcher scouting report?
@api-scout Can you check if the /teams/{id}/stats endpoint returns split data?
```

## Epic/Story Workflow

The project uses a structured planning system. Here is how it works from an operator's perspective.

### Key Concepts

- **Ideas** (`/.project/ideas/`): Lightweight captures of future directions. No stories, no scope, no timeline. Just a thought on file.
- **Epics** (`/epics/E-NNN-slug/`): Structured work with clear scope, stories, and acceptance criteria. An epic groups related stories toward a single goal.
- **Stories** (`/epics/E-NNN-slug/E-NNN-SS-slug.md`): Individual units of work with specific acceptance criteria. Each story is assigned to one implementing agent.

### Workflow States

**Epics**: `DRAFT` -> `READY` -> `ACTIVE` -> `COMPLETED`

- `DRAFT`: PM is still forming the epic (consulting domain experts, writing stories).
- `READY`: Refinement is complete. Stories have acceptance criteria and are dispatchable.
- `ACTIVE`: At least one story is in progress.
- `COMPLETED`: All stories are done and verified.

**Stories**: `TODO` -> `IN_PROGRESS` -> `DONE`

### How to Request Work

1. **Describe the need** to the product-manager. Be specific about the outcome you want, not the implementation.
2. The PM creates or updates an epic with stories.
3. Tell the PM to **dispatch** when you are ready to execute: "dispatch epic E-028" or "start the next story."
4. The PM creates an Agent Team, spawns implementing agents, and coordinates the work.
5. When stories complete, the PM verifies acceptance criteria and marks them done.

### How to Check Status

- **Active epics**: Look in `/epics/` for epic directories. The epic file's Stories table shows the status of each story.
- **Archived epics**: Completed work moves to `/.project/archive/`.
- **Ideas backlog**: Future directions are captured in `/.project/ideas/README.md`.

You can also ask the PM directly: "What is the status of epic E-028?" or "What stories are in progress?"

## Creating a New Agent

New agents are created by the **claude-architect**. If you need a new specialist:

1. Describe the role and responsibilities to the claude-architect.
2. The architect creates the agent definition file in `.claude/agents/`, following established patterns for tool access, model selection, and prompt structure.
3. The architect updates `CLAUDE.md` to include the new agent in the ecosystem table.

Agent definitions are markdown files with YAML frontmatter that specify the agent's name, model, tools, and behavioral prompt.

---

*Last updated: 2026-03-03 | Story: E-028-03*
