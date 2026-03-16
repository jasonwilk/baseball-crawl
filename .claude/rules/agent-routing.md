---
paths:
  - "**"
---

# Agent Routing

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

**Routing Precedence**: If a story's "Files to Create or Modify" includes any context-layer path listed above, route to `claude-architect` regardless of the story's primary domain or Agent Hint value. The only exception is PM updating its own memory files (`.claude/agent-memory/product-manager/`) during normal closure work.

## Decision Routing

When a decision arises during any workflow (planning, dispatch, consultation, or ad-hoc work), route it to the owning agent. Advisory consultants may be invoked for additional perspective but the owner has final authority in their domain.

| Decision Domain | Owner | Advisory Consultants |
|----------------|-------|---------------------|
| Work definition, priority, acceptance criteria, story scope | **product-manager** | baseball-coach (coaching value), claude-architect (feasibility) |
| Context-layer architecture (agents, rules, skills, hooks, CLAUDE.md) | **claude-architect** | product-manager (scope alignment) |
| Domain requirements, coaching value, stat definitions | **baseball-coach** | product-manager (prioritization) |
| API behavior, endpoint schemas, credential patterns | **api-scout** | software-engineer (implementation implications) |
| Database schema, ETL pipelines, query optimization | **data-engineer** | baseball-coach (data requirements), software-engineer (implementation) |
| Python implementation, testing, code architecture | **software-engineer** | data-engineer (schema constraints), api-scout (API details) |
