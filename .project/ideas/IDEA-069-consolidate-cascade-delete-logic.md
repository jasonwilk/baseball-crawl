# IDEA-069: Consolidate cascade delete logic between admin route and reports path

## Status
`CANDIDATE`

## Summary
`src/api/routes/admin.py::_delete_team_cascade` and `src/reports/generator.py::cascade_delete_team` both implement cross-perspective cascade delete logic for team removal. The generator.py version uses a canonical helper `_delete_game_scoped_data_for_perspectives` (lines 1306-1390) with a `NOT EXISTS (game_perspectives)` guard. The admin.py version currently duplicates (and drifted from) this pattern. E-221-05 fixes the admin cascade in place to match the canonical pattern, but leaves the duplication. This idea captures the refactor to delegate the admin cascade to the generator.py helper as a single source of truth.

## Why It Matters
The duplication is exactly the pattern that caused E-220's 8 rounds of remediation — two code paths with subtly different behavior diverging over time. E-221-05 itself is evidence: the admin cascade had already drifted from the generator path and was missing both Phase 1a perspective scoping and a Phase 2 NOT EXISTS guard. A single canonical helper eliminates the divergence risk class and forces future cascade-delete invariants to land in exactly one place.

## Rough Timing
Defer until one of:
- There's another reason to touch the admin cascade (natural consolidation opportunity)
- We observe another divergence-induced bug between the two paths
- A dedicated refactoring pass is scheduled

## Dependencies & Blockers
- [ ] E-221-05 must land first (provides the in-place fix that this refactor will consolidate)

## Open Questions
- Should the canonical helper be moved from `src/reports/generator.py` to a neutral module (e.g., `src/db/cascade.py`) so neither caller "owns" it?
- The admin cascade has `confirm_cross_perspective` informed-consent flags that the reports cascade doesn't need — how does that live in a shared helper? Parameter, wrapper, or split responsibility at the caller boundary?

## Notes
Source: E-221-05 scope expansion discussion (Option C path).

Related: E-221 (parent epic), E-220 round 7 (where the reports-path helper was canonized), R8-P1-1 (the admin cascade drift that forced E-221-05's scope expansion).

---
Created: 2026-04-12
Last reviewed: 2026-04-12
Review by: 2026-07-12
