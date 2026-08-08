# IDEA-115: Codify grep-and-reconcile as the standing eviction discipline (hand-listed eviction sets systematically undercount)

## Status
`CANDIDATE`

## Summary
When an epic DELETES or RENAMES a command, table, column, function, or file, the references to it are scattered across code, docs, context-layer rules, and agent memory. This session showed — three separate times in one planning cycle — that a **hand-enumerated** eviction list systematically undercounts, and each round of review (holistic, Codex, PM full-repo grep) finds more surfaces the prior list missed. The durable fix already applied ad hoc in E-256/E-259 should be codified as a standing discipline: an eviction/propagation AC MUST be phrased as a **grep-and-reconcile** ("grep the whole repo for the retiring identifier; reconcile every LIVE hit — strike stale, preserve still-valid") with any enumerated surfaces as a **Technical-Notes SEED, not a ceiling**, and reconciliation ROUTED by ownership (code→SE, docs/admin→docs-writer, context-layer→claude-architect, agent-memory→each owning agent, strategic docs→PM).

**Scope reconciliation (2026-07-09):** the **agent-memory-dir half** of this lesson is now DISCHARGED by **E-259-05 AC-6** — it generalizes the Deletion-Side Eviction paragraph in `.claude/rules/context-layer-assessment.md` to grep each agent's own `.claude/agent-memory/<agent>/` dir (MEMORY.md index AND topic files), reconciled by the owning agent, at closure. So the closure-gate / agent-memory portion is shipping; do NOT re-capture it here. The **residual IDEA-115 scope** is the still-uncaptured half: the broader planning-time discipline that eviction/propagation **story ACs** for NON-memory surfaces (the backfill-docs class — a command deletion undercounting its `docs/`, `src/` docstring, `ROADMAP`, and test surfaces) should DEFAULT to grep-and-reconcile-routed-by-ownership. E-256 story 02 APPLIES this per-epic, but it is not yet a standing rule/heuristic for planners. That default is what IDEA-115 carries forward.

## Why It Matters
Three incomplete static-eviction lists in one session is a pattern, not bad luck:
- **E-259 DE-memory sweep**: 1 file (CA) → 2 (Codex) → 4 (PM full-dir grep). *(This memory-dir class is now DISCHARGED by E-259-05 AC-6 — see Scope reconciliation.)*
- **E-256 backfill-appearance-order docs**: 2 surfaces (story) → 5 (Codex +3) → 11 (PM whole-repo grep). *(This non-memory class is the live residual — a command deletion undercounting docs/src-docstrings/ROADMAP/tests.)*
- The `doc-sweep.md` rule already codifies the *prose-synonym* half of this (E-250 "across games and seasons"), but it governs how a doc-consistency sweep VERIFIES a concept — it does not tell a PLANNER to write eviction ACs as grep-and-reconcile in the first place. That gap is what let three static lists ship this session.
A grep-and-reconcile story AC starts a future eviction epic from the complete surface instead of rediscovering the undercount. `context-layer-assessment.md`'s Deletion-Side Eviction paragraph is now the closure-gate + agent-memory home (E-259-05 landed that); the residual gap is a **planning-time AC-authoring heuristic** for NON-memory surfaces — likely `agent-routing.md` or the PM agent definition's quality checklist / consistency-sweep section, not the closure gate.

## Rough Timing
Promote when the next deletion/rename-heavy epic is planned, or fold into a context-layer-discipline pass. No urgency; E-256/E-259 already apply the fix locally. The value is making it the DEFAULT so it is not re-derived each time.

## Dependencies & Blockers
- [ ] None hard. Could ride the next `agent-routing.md` / `context-layer-assessment.md` revision.

## Open Questions
- Which file owns it: a new heuristic in `context-layer-assessment.md` (Deletion-Side Eviction), a line in `agent-routing.md`, or the PM agent definition's quality checklist / consistency-sweep section?
- Should it be a hard AC-authoring rule ("eviction ACs MUST be grep-and-reconcile") or a review-prompt heuristic?
- Does it generalize to non-context-layer eviction (a deleted `src/` symbol's call sites), or stay scoped to the doc/context/memory surface where the undercount pattern showed up?

## Notes
Surfaced by PM during the E-256/E-259 round-2 Codex triage (2026-07-09); the team-lead flagged it as a recurring lesson worth outliving the session. **Domain: claude-architect** (eviction discipline lives in `agent-routing.md` / `context-layer-assessment.md` — CA's context layer). **PARTIALLY DISCHARGED**: the agent-memory-dir half ships in E-259-05 AC-6 (generalizes Deletion-Side Eviction to per-agent dirs); the residual is the planning-time grep-and-reconcile heuristic for NON-memory story ACs (the backfill-docs class E-256 story 02 applied ad hoc). Do not close — the residual is real and uncaptured. Related: `.claude/rules/doc-sweep.md` (prose-synonym verification half), `.claude/rules/context-layer-assessment.md` (Deletion-Side Eviction closure gate — now includes agent-memory dirs via E-259-05), `.claude/rules/tool-output-integrity.md` (Prohibition 3, grep-hit-is-a-candidate-not-a-ruling).

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
