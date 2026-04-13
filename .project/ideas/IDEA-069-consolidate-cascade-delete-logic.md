# IDEA-069: Consolidate cascade delete logic between admin route and reports path

## Status
`PROMOTED`

## Promotion Note
Promoted to E-221-05 on 2026-04-13. Scope absorbed during dispatch after empirical discovery that the admin cascade bug required the consolidation refactor as load-bearing work. The prior in-place fix (Option C, 2026-04-12) proved insufficient: three tests failed in `tests/test_admin_delete_cascade.py`, rooted in missing teams-row retention and cross-perspective orphan cleanup in `admin.py::_delete_team_cascade`. Rather than continue patching the admin cascade in place, the user authorized Option 2 (refactor-delegate): replace the admin cascade's in-place cleanup phases with a delegation call to `src/reports/generator.py::cascade_delete_team` (the canonical helper). This creates a single source of truth for cascade delete logic and eliminates the drift risk class that caused R8-P1-1. See `/epics/E-221-perspective-residuals-and-fixture-audit/E-221-05.md` for the implementation scope and acceptance criteria, and the epic's 2026-04-13 History entry for the decision context.

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
