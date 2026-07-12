# IDEA-125: Extend the Deletion-Side-Eviction grep-target enumeration to all doc trees + `src/` docstrings

## Status
`CANDIDATE`

## Summary
`.claude/rules/context-layer-assessment.md`'s **Deletion-Side Eviction** paragraph enumerates its grep targets as `.claude/rules/`, `.claude/agents/`, `CLAUDE.md`, and (after E-259-05's AC-6 trigger-8 promotion) **each agent's own `.claude/agent-memory/<agent>/` dir**. That enumeration **omits the rest of the `docs/` tree and `src/` docstrings/comments**: `docs/api/`, `docs/ROADMAP.md`, `docs/coaching/` (only `docs/admin/` is routinely swept, and only because a docs-writer runbook story happens to cover it), plus in-code docstrings/comments outside the files a deletion story explicitly lists. Extend the rule's grep-target list to name **ALL doc trees** (`docs/api/`, `docs/ROADMAP.md`, `docs/coaching/` — not just `docs/admin/`) **and `src/` docstrings/comments** as standing eviction targets.

## Why It Matters
The E-259 eviction scope split as story 05 = `.claude/**` + CLAUDE.md and story 06 = `docs/admin/` — a split that **structurally omitted** `docs/api/`, `docs/ROADMAP.md`, and `src/` docstrings. The closure Codex review (F3) then found three genuine stale references to the retired apparatus that the sweep missed: `src/db/player_dedup.py:554` (docstring), `docs/api/flows/opponent-scouting.md:89`, and `docs/ROADMAP.md:97`/`:175`. These were caught only by the post-closure review, not by the eviction itself. Naming the omitted trees in the rule closes the gap at the source: future deletion-side evictions grep every doc tree + `src/` docstrings by default instead of relying on which stories happen to touch which directories.

**Distinct from two adjacent items — this is the FILE-TREE scope, not the discipline or the memory dirs:**
1. **IDEA-115** (grep-and-reconcile eviction discipline) is about *how* to reconcile hits within a scope (token-grep + synonym expansion + semantic read, reconcile-not-strike) — it does not widen *which trees* are grepped.
2. **E-259-05 AC-6** (the trigger-8 promotion) widened the target set to include *each agent's own memory dir* (index AND topic files) — a memory-dir widening, not a doc-tree widening.
This idea names the third axis: the **doc-tree + `src/`-docstring file-tree scope**, and a specific rule edit (extend the enumeration).

## Rough Timing
A deliberate context-layer touch on `context-layer-assessment.md`, routed to **claude-architect**. NOT bundled into the E-259 closure: adding lines to `context-layer-assessment.md` would re-grow the just-set context-ratchet baseline (12229) and re-trip trigger-7 mid-closure — so it belongs in a future context-layer pass with its own offset/signed exception. No urgency (it is a scoping improvement, not a live bug); promote when a context-layer-rules cleanup is next planned, or fold into whatever epic next edits `context-layer-assessment.md`.

## Dependencies & Blockers
- [ ] None hard. Independent of E-259 (E-259's own 3 missed refs are FIXED in its closure remediation; this idea is the systemic rule fix so the next epic does not repeat the omission).

## Open Questions
- Should the enumeration be exhaustive (name each tree) or principled ("every `docs/` subtree + `src/` docstrings/comments")? A principle is drift-proof against new doc trees; an explicit list is easier to grep-verify. Lean: principle + a non-exhaustive "e.g." list.
- Does `src/`-docstring eviction belong in the SAME Deletion-Side-Eviction paragraph, or is it better owned by the code-reviewer "Stale prose reference sweep" Bug-Pattern rule (which already greps docstrings/comments on rename/removal)? Possible the right fix is a cross-reference between the two rather than duplication.

## Notes
Surfaced by the E-259 closure Codex review (finding F3), 2026-07-12. **Domain: claude-architect** (`.claude/rules/context-layer-assessment.md`). Related: [IDEA-115], E-259-05 AC-6 (trigger-8 Deletion-Side-Eviction generalization).

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
