---
paths:
  - "CLAUDE.md"
  - ".claude/rules/*.md"
  - ".claude/agent-memory/*/MEMORY.md"
---

# Context-Layer Guard

This rule defines the placement framework for project context and prevents regression toward a monolithic CLAUDE.md.

## Placement Framework

Each piece of project context belongs in exactly one delivery mechanism:

| Mechanism | What belongs there | Delivery |
|-----------|-------------------|----------|
| **CLAUDE.md** | Genuinely ambient project identity: purpose, scope, stack, deployment target, data philosophy, security rules, key directories, agent ecosystem, git conventions, commands, workflows | Every session, every agent |
| **Scoped rules** (`.claude/rules/*.md`) | Invariants, safety gates, and procedural guidance that fire on matching file paths | Only when an agent touches matching files |
| **Skills** (`.claude/skills/`) | Triggered workflows loaded on demand by user intent phrases | Only when explicitly invoked |
| **Agent definitions** (`.claude/agents/*.md`) | Role-scoped knowledge, responsibilities, anti-patterns, inter-agent coordination | Only for the specific agent |
| **Agent memory** (`.claude/agent-memory/`) | Learned patterns, operational knowledge, domain discoveries | Only for the specific agent |

## CLAUDE.md Target

**~150 lines.** CLAUDE.md holds genuinely ambient project identity only. Before adding content to CLAUDE.md, ask: "Does every agent need this on every interaction?" If the answer is "only when touching certain files" or "only for certain agents," it belongs in a scoped rule or agent definition instead.

## MEMORY.md Target

**Under 150 lines.** MEMORY.md is an index, not a memory store. Content beyond line 200 is silently truncated by the platform. Extract detailed content to topic files in the same directory and link from MEMORY.md.

## New Rule Guidelines

- New rules MUST have `paths:` frontmatter scoping. Universal rules (`paths: "**"`) must justify why they need to load on every interaction.
- Before creating a new rule file, consider whether the content fits in an existing thematic rule (extend rather than create). Single-purpose rules under 15 lines are candidates for consolidation.
