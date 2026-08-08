# IDEA-044: Prevent Duplicate Team Creation

## Status
`PROMOTED`

## Summary
Improve the schedule loader and OpponentResolver to detect and avoid creating duplicate team rows in the first place. Currently, stub teams from the schedule loader and resolved teams from OpponentResolver can create independent rows for the same real-world opponent.

## Why It Matters
E-155 provides the "cure" (merging existing duplicates), but prevention is better than cure. Reducing duplicate creation means less manual admin work and fewer coaching data quality issues.

## Rough Timing
After E-155 ships. The merge tool handles the backlog; prevention stops new duplicates from accumulating. Promote when the admin reports that duplicates keep reappearing after being merged.

## Dependencies & Blockers
- [ ] E-155 (Combine Duplicate Teams) must be complete -- establishes the merge baseline
- [ ] Understanding of all four duplicate creation paths (documented in E-155 Background & Context)

## Open Questions
- Can the schedule loader check for existing teams by name before creating stubs?
- Should OpponentResolver check for existing stubs before creating new resolved rows?
- What's the right dedup key? Name + season_year? public_id? gc_uuid?
- How to handle the race condition between schedule loader and OpponentResolver running concurrently?

## Notes
E-155 discovery identified four creation paths: schedule loader stubs, OpponentResolver resolved teams, manual admin linking, and different root_team_id values mapping to the same school. Each path needs a dedup check.

**Promoted to E-167** (Opponent Dedup Prevention and Resolution) on 2026-03-27. E-167 addresses all four creation paths via a shared `ensure_team_row()` function with a deterministic dedup cascade, plus admin-facing resolution workflow and auto-merge CLI.

---
Created: 2026-03-25
Last reviewed: 2026-03-27
Review by: 2026-06-23
