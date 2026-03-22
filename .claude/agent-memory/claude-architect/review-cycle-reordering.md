---
name: Review cycle reordering
description: Pending update to plan and implement skills -- internal reviews (CR + team) before Codex, with review scorecard pattern
type: project
---

## Approved Direction: Internal Reviews First, Codex as Final Validation

**Status**: Pending context-layer update. Will become a story in a future epic.
**Approved**: 2026-03-22

### The Principle

"Keep iterating until things quiet down" -- advance to the next review tier when the current tier's findings are zero or minor. Cheaper/faster reviews first, expensive external reviews as final validation.

### E-147 Evidence (26 findings, convergence pattern)

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex iteration 1 | 5 | 5 | 0 |
| Codex iteration 2 | 3 | 3 | 0 |
| Code-reviewer pass 1 | 4 | 4 | 0 |
| Holistic team review 1 | 6 | 6 | 0 |
| Code-reviewer pass 2 | 2 | 2 | 0 |
| Holistic team review 2 | 2 | 2 | 0 |
| Codex iteration 3 | 4 | 2 | 2 |
| **Total** | **26** | **24** | **2** |

Key insight: CR and team reviews found different (often more practical) issues than Codex -- wrong function signatures, missing API calls, implementation feasibility gaps. Codex found rubric-level issues (AC testability, dependency declarations). Internal reviews should clean up mechanical issues before Codex runs its systematic rubric pass.

### Plan Skill Changes (`.claude/skills/plan/SKILL.md`)

Current Phase 3-4: Codex spec review → Triage/Refine → loop up to 3x

Proposed restructure:
- **Phase 3 (Internal Review Cycle)**: Code-reviewer spec audit + holistic team review → Triage/Refine → loop (3 iterations max). Spawn CR as infrastructure during Phase 3. Holistic review leverages already-spawned planning team (near-zero cost).
- **Phase 4 (Codex Validation Pass)**: Run codex-spec-review.sh → Triage/Refine → loop (2 iterations max -- spec should be clean by now).
- User decides when to advance from Phase 3 to Phase 4 (judgment call, not automatic gate).

### Implement Skill Changes (`.claude/skills/implement/SKILL.md`)

Current Phase 4: 4a Codex code review → 4b CR integration review

Proposed swap:
- **Phase 4a**: Code-reviewer integration review (fast, cross-story interactions)
- **Phase 4b**: Codex code review (systematic rubric validation, final pass)

Per-story CR in Phase 3 stays unchanged.

### Review Scorecard Pattern

Include a review scorecard table in epic History at the READY gate (planning) and at closure (implementation). Format:

```
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| [pass name] | N | N | N |
| **Total** | **N** | **N** | **N** |
```

This gives visibility into the convergence pattern -- how many passes it took and where findings came from. Encode in plan skill Phase 5 (READY gate) and implement skill Phase 5 (closure).

### Files to Update

1. `.claude/skills/plan/SKILL.md` -- Restructure Phase 3-4, add scorecard to Phase 5
2. `.claude/skills/implement/SKILL.md` -- Swap Phase 4a/4b, add scorecard to Phase 5
3. No new agents, skills, or rules needed
