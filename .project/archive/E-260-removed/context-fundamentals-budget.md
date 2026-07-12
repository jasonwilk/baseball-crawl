# Removed/replaced text snapshot — context-fundamentals/SKILL.md

- **Source:** `.claude/skills/context-fundamentals/SKILL.md`
- **Story:** E-260-04 (Scope-correct context-fundamentals: relay sentence + budget table)
- **Date:** 2026-07-11
- **Original line ranges (pre-edit):** 195 (relay sentence), 74-85 (ambient-budget table, incl. the :80 context-layer-guard reference)

---

## :195 — verbatim-relay sentence (scoped, not deleted)

- **`multi-agent-patterns`** (`.claude/skills/multi-agent-patterns/SKILL.md`): In multi-agent dispatch chains, the context budget concern applies to the dispatch context block (story file + epic Technical Notes). Understanding the budget helps explain why verbatim relay is the right choice even when summarizing would save tokens -- the savings are modest and the loss is real.

---

## :74-85 — ambient-budget table (re-derived; stale "~614-886 / measured post-E-213 (2026-04-05)" replaced)

Every baseball-crawl agent session starts with approximately **614-886 lines of always-loaded ambient context** before any task-specific content is loaded:

| Source | Approximate Size | Notes |
|--------|-----------------|-------|
| Root `CLAUDE.md` | ~156 lines | Project identity, stack, deployment, security, architecture (1-line invariants), commands |
| Universal rules (6 files) | ~303 lines total | workflow-discipline (98), agent-team-compliance (52), dispatch-pattern (52), agent-routing (37), worktree-isolation (35), vision-signals (29) |
| Triggered rules (0-24 files) | ~0-400 lines | Scoped by `paths:` frontmatter; loads only when matching files are touched. Highest for `src/gamechanger/` edits (~200+ lines: http-discipline, testing, api-docs, key-metrics, architecture-subsystems), lowest for context-layer edits (~36 lines: context-layer-guard, which scopes to `CLAUDE.md`, `.claude/rules/*.md`, and `.claude/agent-memory/*/MEMORY.md`) |
| Agent definition (`.claude/agents/<agent>.md`) | ~125-315 lines | Varies by agent; code-reviewer is largest (315), claude-architect smallest (125) |
| Agent `MEMORY.md` (`.claude/agent-memory/<agent>/MEMORY.md`) | ~30-112 lines | Varies; ux-designer ~112, PM ~78, docs-writer ~30 |
| **Total ambient** | **~614-886 lines** | Always-loaded context before any task begins |

These are actuals measured post-E-213 (2026-04-05). Triggered rules add 0-400 lines on top depending on files touched. Check the actual files if precision matters for a specific decision.
