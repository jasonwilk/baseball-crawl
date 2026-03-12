# IDEA-022: Scouting Flow Doc / Schema Stat Mismatch

## Status
`CANDIDATE`

## Summary
The opponent scouting flow doc (`docs/api/flows/opponent-scouting.md`) lists stats that are not present in the actual database schema. The doc describes what the API returns; the schema stores a subset. Either the doc should be corrected to reflect what we actually store, or the schema should be expanded to capture the additional stats.

## Why It Matters
A coach or developer reading the flow doc would expect certain stats to be available in the database, but they aren't. This creates a misleading contract between the documentation and the data layer. As scouting dashboards are built, this mismatch would surface as confusing gaps.

## Rough Timing
Before scouting dashboards go live to coaching staff. Not urgent while only the operator uses `bb data scout`.

## Dependencies & Blockers
- [ ] E-098 (scouting pipeline bug fixes) should be complete first
- [ ] A coaching analytics story or dashboard epic would be the natural vehicle for schema expansion

## Open Questions
- Which stats in the flow doc are missing from the schema? (Needs a concrete audit)
- Should we fix the doc (remove unlisted stats) or expand the schema (add the stats)? DE recommended fixing the doc first, flagging missing stats as future coaching analytics work.
- Does the baseball-coach agent have an opinion on which additional stats are worth storing?

## Notes
- Discovered during Codex code review of E-097+E-098 changeset (P3 finding).
- SE and DE both confirmed real; both recommended docs-writer or future analytics epic, not E-098 scope.
- Related to IDEA-008 (plays/line scores) and IDEA-009 (per-player game stats) which would also expand the schema.

---
Created: 2026-03-12
Last reviewed: 2026-03-12
Review by: 2026-06-12
