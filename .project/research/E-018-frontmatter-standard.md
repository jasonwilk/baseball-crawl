# E-018 Frontmatter Standard

## Decision Date
2026-03-02

## Context
Four agent configuration files (api-scout, baseball-coach, general-dev, data-engineer) have incomplete YAML frontmatter. This document defines the canonical frontmatter standard for all agents in the baseball-crawl project, based on:
- The Claude Code subagent documentation (https://code.claude.com/docs/en/sub-agents)
- The orchestrator and product-manager as reference implementations
- Analysis of each agent's actual role and tool needs

## Decisions

### 1. Description Field Standard

**Decision**: Descriptions must be 1-3 concise sentences that tell Claude when to delegate to this agent. No multi-line examples, no "Use this agent when..." followed by a semicolon-delimited list of scenarios, no embedded Example blocks.

**Rationale**: Per the Claude Code docs, the `description` field answers "When Claude should delegate to this subagent." The orchestrator's routing table in CLAUDE.md already provides detailed routing logic. Agent-level descriptions need only identify the agent's domain clearly enough for Claude to match requests.

**Pattern**: `"[Role description]. [Key domain/trigger]. [Boundary statement if needed]."`

**Recommended descriptions for each target agent:**

- **api-scout**: `"GameChanger API exploration, endpoint documentation, and credential management specialist. Probes API endpoints, documents responses in docs/gamechanger-api.md, and guides credential rotation."`

- **baseball-coach**: `"Baseball analytics domain expert and coaching requirements translator. Defines what statistics and data matter for coaching decisions, validates schemas and features against real coaching needs, and designs scouting report formats."`

- **general-dev**: `"Python implementation agent for crawlers, parsers, loaders, utilities, and tests. Executes stories by writing code against specifications produced by other agents. Requires a story reference before beginning any work."`

- **data-engineer**: `"Database schema design, SQL migration management, ETL pipeline architecture, and query optimization specialist. Designs and implements the data layer against coaching analytics requirements. Requires a story reference before beginning any work."`

### 2. Tools Field Standard

**Decision**: Every agent MUST have an explicit `tools` field. Even agents that need broad tool access should list their tools explicitly rather than relying on implicit inheritance.

**Rationale**: Per the Claude Code docs best practice -- "Limit tool access: grant only necessary permissions for security and focus." Explicit tool lists serve as documentation of each agent's capabilities and prevent accidental access to tools an agent does not need.

**Exception**: Implementing agents (general-dev, data-engineer) that need essentially all tools may omit `tools` to inherit everything, but MUST include a YAML comment explaining this is intentional. However, the preferred approach is to be explicit.

**Recommended tools per agent:**

- **api-scout** (consultative + execution):
  ```yaml
  tools:
    - Read
    - Write
    - Edit
    - Bash
    - Glob
    - Grep
    - WebFetch
  ```
  Rationale: Needs Bash to execute curl commands and test API endpoints. Needs Read/Write/Edit to maintain the API spec at `docs/gamechanger-api.md`. Needs Glob/Grep to search for related files. Needs WebFetch for API documentation research. Does NOT need Task/Agent (does not delegate to other agents).

- **baseball-coach** (consultative, read-heavy):
  ```yaml
  tools:
    - Read
    - Write
    - Edit
    - Glob
    - Grep
  ```
  Rationale: Needs Read to review story files, epic Technical Notes, and schema docs. Needs Write/Edit to produce requirements documents and update memory. Needs Glob/Grep to find relevant files. Does NOT need Bash (no code execution), Task/Agent (does not delegate), or WebFetch (domain knowledge is internal).

- **general-dev** (full implementing agent):
  ```yaml
  tools:
    - Read
    - Write
    - Edit
    - Bash
    - Glob
    - Grep
    - WebFetch
  ```
  Rationale: Needs all file tools and Bash for implementation work. Needs WebFetch for library documentation research. Does NOT need Task/Agent (does not delegate to other agents; it receives work, not dispatches it).

- **data-engineer** (full implementing agent):
  ```yaml
  tools:
    - Read
    - Write
    - Edit
    - Bash
    - Glob
    - Grep
    - WebFetch
  ```
  Rationale: Same as general-dev. Needs all file tools and Bash for writing migrations, testing SQL, and implementing ETL code. Does NOT need Task/Agent.

### 3. Skills Field Standard

**Decision**: Do NOT use the `skills` frontmatter field for preloading. Continue with on-demand loading via system prompt instructions.

**Rationale**: Per the Claude Code docs -- "The full content of each skill is injected into the subagent's context at startup." This means every preloaded skill consumes context window tokens on every invocation, regardless of whether the skill is needed for that particular task. The current agents reference 2-3 skills each, but use them conditionally (e.g., "Load when context window is above 70%"). Preloading would waste context on tasks that do not trigger those conditions.

**Implementation**: Keep existing "Load `.claude/skills/...` when:" directives in the system prompt body. No changes needed.

### 4. Other Frontmatter Fields

**Decision**: Do NOT add `maxTurns`, `permissionMode`, `hooks`, `isolation`, or `background` to any of the four target agents.

**Rationale for each:**

- **maxTurns**: No evidence that any agent runs away with excessive turns. If this becomes a problem, it can be added per-agent. Adding it preemptively risks cutting agents off mid-task.
- **permissionMode**: The default permission checking is appropriate for all agents. Consultative agents (api-scout, baseball-coach) should not auto-bypass permissions. Implementing agents need human-in-the-loop for destructive operations.
- **hooks**: No subagent-scoped lifecycle hooks are needed. The project's statusline hook runs at the session level, not the subagent level.
- **isolation**: No agent needs git worktree isolation. All agents work on the same codebase.
- **background**: No agent should default to background execution. The PM and orchestrator decide whether to run agents in foreground or background based on the task.

### 5. Routing Examples Disposition

**Decision**: Remove the routing examples entirely from the description fields. Do NOT relocate them to the system prompt body.

**Rationale**: The routing examples served the `description` field's purpose of telling Claude when to delegate, but they are redundant with:
1. The orchestrator's routing table in its system prompt (which maps request categories to agents)
2. The concise descriptions (Decision 1 above), which provide sufficient routing information
3. CLAUDE.md's Agent Ecosystem section, which lists all agents and their domains

The system prompt body already describes what each agent does in detail. Adding routing examples to the body would duplicate information without improving agent behavior.

### 6. Required Frontmatter Fields (Canonical Set)

Every agent in this project MUST have these frontmatter fields:
1. `name` (required per docs)
2. `description` (required per docs, 1-3 concise sentences)
3. `model` (explicit model selection)
4. `color` (visual identification)
5. `memory` (persistent knowledge scope -- `project` for all agents in this repo)
6. `tools` (explicit capability scoping)

Optional fields are added only when a specific agent needs them.

### 7. Frontmatter Ordering Convention

Fields should appear in this order for consistency across all agent files:
```yaml
---
name: agent-name
description: "Concise routing trigger description."
model: sonnet
color: blue
memory: project
tools:
  - Tool1
  - Tool2
---
```

## Reference Comparison

### Before (current api-scout):
```yaml
---
name: api-scout
description: "GameChanger API exploration... [25+ lines with 5 examples]"
model: sonnet
color: orange
memory: project
---
```

### After (target api-scout):
```yaml
---
name: api-scout
description: "GameChanger API exploration, endpoint documentation, and credential management specialist. Probes API endpoints, documents responses in docs/gamechanger-api.md, and guides credential rotation."
model: sonnet
color: orange
memory: project
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
---
```

## Open Items
- The claude-architect and product-manager agents also lack explicit `tools` fields. This is noted but out of scope for E-018 (per the epic's Non-Goals). A follow-up epic or idea may address those.
- The orchestrator is missing the `memory` field. This is by design -- it is a routing-only agent that does not need persistent knowledge.
