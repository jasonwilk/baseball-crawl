# Agent Guide

## Overview

Baseball-crawl uses an ecosystem of AI agents (powered by Claude Code) to manage development. Each agent has a specific role -- product management, coding, API exploration, domain expertise, documentation, or infrastructure -- and they collaborate through a structured epic/story workflow.

The agent ecosystem exists because the project is primarily developed through AI-assisted workflows. Rather than a single general-purpose AI, the work is split across specialized agents with focused prompts, appropriate tool access, and clear responsibilities. This keeps context windows manageable and output quality high.

Agent definitions live in `.claude/agents/`. Rules governing their behavior live in `.claude/rules/`. Memory files that persist across sessions live in `.claude/agent-memory/`.

## Agents

| Agent | Alias | Model | Role |
|-------|-------|-------|------|
| **product-manager** | PM | Opus (1M context) | Owns what to build, why, and in what order. Creates epics and stories, prioritizes the backlog, owns story/epic statuses, verifies acceptance criteria, and closes completed work. Never writes code. |
| **claude-architect** | | Opus (1M context) | Designs and manages agents, `CLAUDE.md`, rules, skills, and hooks. Maintains the agent ecosystem itself. |
| **baseball-coach** | coach | Sonnet | Domain expert. Translates coaching needs into technical requirements, validates schemas against real coaching use cases, and defines what statistics matter. |
| **api-scout** | | Opus | Explores the GameChanger API, documents endpoints in `docs/api/endpoints/`, and guides credential rotation. |
| **data-engineer** | DE | Opus (1M context) | Designs database schemas, SQL migrations, and ETL pipelines. Informs the data layer from both domain requirements and API discoveries. |
| **software-engineer** | SE | Opus (1M context) | Implements Python code: crawlers, parsers, loaders, tests, utilities. Works from specifications produced by other agents. |
| **docs-writer** | | Sonnet | Writes and maintains human-readable documentation for admin/developer and coaching staff audiences. |
| **ux-designer** | | Sonnet | Designs layouts, wireframes, and component structure for the reports serving surfaces (report layout, trust surfaces, tools-hub IA). Produces text-based design artifacts that software-engineer implements. |
| **code-reviewer** | | Opus (1M context) | Adversarial code reviewer. Audits implementer work against acceptance criteria and code quality standards before a story can be marked DONE. Finds issues but never fixes them. Spawned automatically for every dispatch -- not assigned stories. |

## How to Work with Agents

### The Product Manager as Entry Point

For most work, start by talking to the **product-manager**. The PM is the coordinator:

- Tell the PM what you want built, fixed, or investigated.
- The PM discovers requirements and writes epics and stories with acceptance criteria. When you authorize dispatch, the main session spawns the specialist agents the stories need (see "How to Request Work" below).
- The PM manages story statuses and verifies acceptance criteria when work is complete.

**Example**: "I want a scouting report that shows the opposing pitcher's K/9 and BB/9 splits." The PM would consult the baseball-coach for requirements, check with data-engineer on schema readiness, and write stories for software-engineer to implement.

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
4. During dispatch, the **main session** (the agent you are talking to) is the spawner and router, not the PM: it creates the epic worktree, spawns the specialist agents the stories need plus PM and code-reviewer as standing infrastructure, assigns stories serially, and routes each one through review. The PM cannot spawn other agents itself -- it owns story/epic statuses and acceptance-criteria verification, never the spawning.
5. Each story is reviewed once against a frozen snapshot of its changes: code-reviewer issues a review verdict (for stories touching code or docs), and the PM issues the acceptance-criteria verdict (for every story, every domain). See "Review Tiers and Verdicts" below.
6. Once a story's required verdicts approve, it is marked DONE and the main session stages its changes before starting the next story.

### Review Tiers and Verdicts

Per-story review depth is determined mechanically from the story's file paths, not by judgment call. Every path a story touches falls into one of three tiers, and a story takes the highest tier present among its files:

- **Tier A** -- executable and infrastructure paths: `src/`, `tests/`, `migrations/`, `scripts/`, `.claude/hooks/`, `.githooks/`, `Dockerfile`, `docker-compose*.yml`, dependency files, `.devcontainer/`. Any path matching none of the classes below also falls into tier A by default (fail-safe: an unclassified path gets the deepest review, not the shallowest).
- **Tier B** -- `docs/`.
- **Tier C** -- everything else under `.claude/**` (except `.claude/hooks/`), plus `CLAUDE.md`, `epics/**`, and `.project/**`.

Tier A and B stories get a per-story review verdict from code-reviewer, issued in parallel with the PM's acceptance-criteria verdict. Tier C stories (pure context-layer changes) skip the per-story code-reviewer verdict -- PM's AC verdict stands alone -- but tier C content is still reviewed once, at epic closure, as part of the unconditional closure integration review. **Each verdict is issued exactly once against a given frozen story state and is never re-asked**; a remediation round produces a new frozen state and gets its own first verdict, not a repeat of the old one.

Agents' `SendMessage` completion reports follow a fixed schema (Files Changed, Test Results, Behavioral Changes, plus role-specific sections) capped around 6,000 characters, to keep reports from ballooning with restatement. code-reviewer is deliberately excluded from that cap, since its report length is driven by finding count and a length limit risks truncating a real finding.

The context-layer's overall size is no longer gated against a committed baseline. Growth is now assessed on a schedule instead: a periodic refinement pass every five epic closures (which prunes and re-homes context-layer content) and a batched adversarial audit every three closures. `.claude/hooks/context-ratchet.sh` survives as an on-demand line-count diagnostic, not a pass/fail gate.

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

*Last updated: 2026-08-02 | Source: E-280 (agent table corrections -- ux-designer and code-reviewer added, model attributions fixed; dispatch spawning corrected to main-session-as-spawner; review-tier/verdict and context-layer-gate-retirement sections added)*
