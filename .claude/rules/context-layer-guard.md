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

## CLAUDE.md Scope

CLAUDE.md holds genuinely ambient project identity only. Before adding content to CLAUDE.md, ask: "Does every agent need this on every interaction?" If the answer is "only when touching certain files" or "only for certain agents," it belongs in a scoped rule or agent definition instead. There is no unenforced prose line target here: CLAUDE.md growth is visible in the operator-reviewed closure diff, and the four context-layer subtrees are bounded by the ratchet (`.claude/hooks/context-ratchet.sh`, see `.claude/rules/context-layer-assessment.md` trigger 7).

## MEMORY.md Scope

MEMORY.md is an index, not a memory store: the platform silently truncates content beyond line 200, so extract detailed content to topic files in the same directory and link from MEMORY.md. MEMORY.md files live under `.claude/agent-memory`, so their line counts are priced by the ratchet baseline -- there is no separate unenforced line target.

## New Rule Guidelines

- New rules MUST have `paths:` frontmatter scoping. Universal rules (`paths: "**"`) must justify why they need to load on every interaction.
- Before creating a new rule file, consider whether the content fits in an existing thematic rule (extend rather than create). Single-purpose rules under 15 lines are candidates for consolidation.
- **Don't steer when you can define.** Scoped rules define principles for an area -- they don't steer implementation into that area. A rule loading on `dashboard.py` says "if you're working here, keep this principle in mind," not "you should add this feature here." A rule's `paths:` frontmatter controls when it LOADS into context, not what gets ADDED to the matched files. Do not flag a rule's scope as contradicting a "non-goal" simply because the rule loads on files the non-goal excludes from modification.
