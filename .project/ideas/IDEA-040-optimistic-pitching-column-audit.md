# IDEA-040: Optimistic Pitching Column API Audit

## Status
`CANDIDATE`

## Summary
Investigate which of the 23 "optimistic" pitching columns (mapped by E-117-03 via `defense.get()`) the GameChanger season-stats API actually returns. These columns are in the DDL and mapped in the loader, but have never been confirmed in a live API response.

## Why It Matters
E-117-03 maps 23 pitching columns optimistically — if the API never returns them, they stay NULL forever. Knowing which ones actually populate lets us: (1) confirm data coverage for coaching dashboards, (2) identify any columns that should be removed from dashboard views because they're always NULL, (3) validate the stat glossary's pitching field list against reality.

## Rough Timing
After E-117 ships and a full data re-seed has run. At that point, a simple SQL query (`SELECT COUNT(*) FROM player_season_pitching WHERE col IS NOT NULL`) would also reveal coverage — but an api-scout investigation would confirm the API contract directly.

## Dependencies & Blockers
- [ ] E-117-03 must be complete (columns mapped in loader)
- [ ] Full data re-seed must have run (so season-stats have been fetched)

## Open Questions
- Which of these 23 columns does the API actually return? gp, w, l, sv, bs, r, sol, lob, pik, total_balls, lt_3, first_2_out, lt_13, bbs, lobb, lobbs, sm, sw, weak, hard, lnd, fb, gb
- Are any of these fields returned under a different API key than expected?
- Does coverage differ between seasons or between teams with different subscription tiers?

## Notes
The 23 columns are listed in E-117 epic Technical Notes under "Expected-in-API / optimistic." The glossary (`docs/gamechanger-stat-glossary.md`) lists many of these as "editable pitching stats" which suggests GC tracks them, but presence in the editable list doesn't guarantee they appear in the API response.

This is an api-scout investigation task — not a code change.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
