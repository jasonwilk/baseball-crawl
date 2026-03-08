---
paths:
  - "epics/**"
  - ".project/archive/**"
---

# Context-Layer Assessment Rules

## Purpose

After every epic, evaluate whether the work produced conventions, decisions, boundaries, or knowledge that should be codified in the context layer (CLAUDE.md, agent definitions, rules, skills, hooks, agent memory). This assessment runs independently of the documentation assessment -- both gates must pass before an epic can be archived.

## Assessment Triggers

The main session evaluates each trigger with an explicit **yes** or **no** verdict. All six verdicts are recorded in the epic's History section.

1. **New convention, pattern, or constraint established.** Did the epic introduce a coding pattern, naming convention, file organization rule, or operational constraint that future work should follow?
2. **Architectural decision with ongoing implications.** Did the epic make a technology choice, integration pattern, or structural decision that affects how future epics are planned or implemented?
3. **Footgun, failure mode, or boundary discovered.** Did the epic reveal a gotcha, a common mistake, or an operational boundary (host vs container, auth vs public, etc.) that agents could trip over in future work?
4. **Change to agent behavior, routing, or coordination.** Did the epic modify how agents are dispatched, what they can do, how they communicate, or how the closure sequence works?
5. **Domain knowledge discovered that should influence agent decisions in future epics.** Did the epic surface baseball domain insights, API behavior patterns, or data model knowledge that agents should carry forward?
6. **New CLI command, workflow, or operational procedure introduced.** Did the epic add a new `bb` subcommand, a new script, a new skill, or a new operational workflow that should be documented in the context layer?

## Assessment Procedure

1. After all stories are DONE and the documentation assessment is complete, the main session evaluates each of the six triggers above.
2. For each trigger, record an explicit **yes** or **no** verdict in the epic's History section. A blanket "no context-layer impact" without per-trigger verdicts is **not sufficient** -- every trigger must be individually evaluated.
3. **If any trigger is "yes"**: Spawn `claude-architect` (if not already on the team) to codify the findings in the appropriate context-layer files (CLAUDE.md, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/agent-memory/`). The epic MUST NOT be archived until the codification is complete.
4. **If all triggers are "no"**: Record the per-trigger verdicts in the epic's History section and proceed to archival.

## Blocking Semantics

The epic MUST NOT be archived until the context-layer assessment is complete and any required codification is done. This gate is independent of the documentation assessment gate -- both must pass.

## Context-Layer File Ownership

| Files | Owner |
|-------|-------|
| `CLAUDE.md` | claude-architect |
| `.claude/rules/*.md` | claude-architect |
| `.claude/agents/*.md` | claude-architect |
| `.claude/skills/**` | claude-architect |
| `.claude/hooks/**` | claude-architect |
| `.claude/agent-memory/**` | claude-architect (structure); individual agents (content) |
| `.claude/settings.json`, `.claude/settings.local.json` | claude-architect |
