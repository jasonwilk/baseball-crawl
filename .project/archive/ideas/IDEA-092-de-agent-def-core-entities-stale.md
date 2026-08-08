# IDEA-092: data-engineer.md Core Entities table is stale vs the live schema

## Status
`DISCARDED` (2026-07-12) — the cited DEFECT (hallucination anchors: `PlayerTeamSeason` etc.) was already stripped by E-250-04. CA verified `.claude/agents/data-engineer.md:105-118` now names ONLY real tables and carries a self-aware note at `:118`. Briefly folded into E-262 (story E-262-05) then dropped in review: the residual "fuller schema-aligned entity refresh" is an ENHANCEMENT, not a live defect, and is barred by the E-260 meta-layer freeze. Re-file against a concrete CURRENT inaccuracy (name the mis-described row) if one surfaces.

## Summary
The `.claude/agents/data-engineer.md` "Core Entities" table is broadly out of date with the live database schema — beyond the cross-season/`PlayerTeamSeason` cells that E-250 removes, other rows (e.g. `Lineup`, `PlateAppearance`, and the entity set generally) do not match the tables that actually exist. Refresh the table to reflect the live schema.

## Why It Matters
The DE agent definition is loaded into the data-engineer's context on every spawn, so a stale entity table is a hallucination anchor: it names tables that don't exist (`PlayerTeamSeason` was the flagged one) and mis-describes the ones that do. E-250-04 removes only the cross-season/`PlayerTeamSeason` cells in scope; the rest of the table's drift is real but out of E-250's focused scope. Left uncorrected, it keeps steering DE toward a schema that isn't there.

## Rough Timing
Next time the DE agent definition is touched, or when a data-modeling epic would benefit from an accurate entity map. Low urgency — no active harm beyond the ambient drift, and E-250 removes the most dangerous (non-existent-table) cells.

## Dependencies & Blockers
- [ ] E-250-04 lands first (removes the cross-season/`PlayerTeamSeason` cells) so this cleanup starts from the trimmed table, not the pre-E-250 one.
- [ ] Requires a current-schema pass (`migrations/001_initial_schema.sql` + subsequent migrations, and `.claude/rules/data-model.md`) to rebuild the entity list accurately.

## Open Questions
- Full rewrite of the Core Entities table vs. targeted per-row corrections?
- Should the table cross-link to `.claude/rules/data-model.md` (the authoritative schema-decisions doc) rather than duplicating entity descriptions that will re-drift?

## Notes
Surfaced by claude-architect's context-layer inventory during E-250 planning (Flag B, 2026-07-03). Deliberately kept OUT of E-250 to avoid sprawling a focused cross-season de-scope epic into a full agent-def rewrite (team-lead direction). Routes to claude-architect (context-layer) when promoted. Related: E-250-04.

---
Created: 2026-07-03
Last reviewed: 2026-07-03
Review by: 2026-10-01
