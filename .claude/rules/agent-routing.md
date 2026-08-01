---
paths:
  - "**"
---

# Agent Routing

## Agent Selection for Dispatch

| Story Domain | Agent Type |
|-------------|-----------|
| Python implementation, crawlers, parsers, tests | `software-engineer` |
| Database schema, SQL migrations, ETL | `data-engineer` |
| API exploration, endpoint docs | `api-scout` |
| Context-layer files: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/**` | `claude-architect` |
| Documentation (`docs/admin/`, `docs/coaching/`) | `docs-writer` |
| UI/UX design: wireframes, layout specs, component inventories, user flows | `ux-designer` |
| Code review (automatic -- not routed by story domain) | `code-reviewer` (spawned automatically by the implement skill for every dispatch; not assigned stories) |

**Read-only tracing/diagnosis routes to the built-in `Explore` agent.** A read-only investigation (trace a call path, locate where a behavior lives, answer "where/how is X done") goes to `Explore`, not to a heavier full-tool `general-purpose` spawn. No new investigator agent is needed -- `Explore` already fits.

**Model escalation -- spawn `model: fable` for adversarial work.** Use a Fable subagent for adversarial verification, independent audits, and contested-design arbitration: task shapes where a fresh strongest-tier context has repeatedly found what same-tier review missed. The Fable audit found the E-276 health-gate CRITICAL after two same-tier epics missed it, and `redteam-e276` found the AC-14 unsatisfiability after six same-tier review passes. Do NOT escalate routine dispatch or bounded implementation -- Opus dispatch on a settled spec measures at baseline steering burden (E-270, E-276). When you do escalate, compose the spawn prompt in the target model's style: give the reason behind the request rather than the request alone, prefer brief instructions to exhaustive enumerations, and include a ground-progress-claims clause — the vendor's exact wording for that clause is transcribed in claude-architect's `model-behavior-reference.md`, so copy it rather than improvising one. **The spawn prompt is the only reliably model-matched surface** -- the harness's injected coaching does not reliably follow an overridden subagent model (verified 2026-07-26: an agent running `claude-opus-5` received a Fable identity block). Per-model style detail is in claude-architect's `model-behavior-reference.md`. (A Claude Code maintainer publishes the same practice -- "use fable subagents when you need more intelligence" -- as corroborating practice, not as the authority for this rule.)

**Dispatch Team metadata**: Epics may include a `## Dispatch Team` section (between Stories and Technical Notes) that explicitly lists the agents needed for the epic. When this section is present and non-empty, the main session should prefer it over inferring agents from story domains using the table above. When the section is absent or empty, the main session determines required agents from the routing table. The main session retains final routing authority -- the Dispatch Team section is advisory.

**Agent Hint**: Stories may carry an optional `## Agent Hint` field that declares which agent type should implement the story. When an Agent Hint is present, the main session should prefer it over file-path inference from the routing table above. The hint is advisory -- the main session may override it based on team composition, agent availability, or other factors.

**Routing Precedence**: If a story's "Files to Create or Modify" includes any context-layer path listed above, route to `claude-architect` regardless of the story's primary domain or Agent Hint value. The sole exception is an agent editing files within its OWN agent-memory directory (`.claude/agent-memory/<agent-name>/`): each agent owns its own learned-knowledge directory, so such edits stay with that agent rather than routing to `claude-architect` (e.g., PM updating `.claude/agent-memory/product-manager/` during closure, or baseball-coach correcting a model doc in `.claude/agent-memory/baseball-coach/`). This carve-out covers an agent's OWN directory only -- a story touching a different agent's memory, or any non-memory context-layer path, still routes to `claude-architect`. It mirrors the own-memory carve-out already in `.claude/rules/workflow-discipline.md` (Consultation Mode Constraint).

**Ceiling on a closure archive-path repoint (a tightening of the carve-out above, not a new grant):** when the closure archive rename strands a path reference in another agent's file, **the only bytes that may change are the path literal.** Rewording, retiring a claim, updating a verdict or adjusting a rating remains the owning agent's. **If the repoint cannot be made without touching more, it is not a repoint** — route it to the owner or capture it as an idea.

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
