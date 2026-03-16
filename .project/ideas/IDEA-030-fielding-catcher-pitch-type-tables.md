# IDEA-030: Fielding, Catcher, and Pitch Type Tables

## Status
`CANDIDATE`

## Summary
Add schema tables and loaders for fielding stats, catcher stats, and pitch type breakdowns. E-100 explicitly deferred these as "purely additive (no FK references from other tables), doesn't block anything."

## Why It Matters
- Fielding stats (errors, putouts, assists, fielding percentage) matter for defensive evaluation and position assignments.
- Catcher stats (caught stealing, passed balls, pickoffs) are critical for evaluating the battery.
- Pitch type breakdowns (fastball/curve/change percentage, velocity) are high-value scouting data if the API provides them.

## Rough Timing
After IDEA-028 (base stat population). These are additive tables with no FK dependencies on existing tables. Promote when:
- A coach asks for defensive stats or catcher metrics
- The season-stats endpoint's defense section is fully documented (fielding vs. catcher vs. pitching fields)
- Pitch type data availability is confirmed via api-scout

## Dependencies & Blockers
- [ ] IDEA-028 (base stat population) — establish the stat mapping pattern first
- [ ] API documentation: confirm which fielding/catcher fields the season-stats endpoint returns
- [ ] API documentation: confirm whether pitch type data exists in any endpoint

## Open Questions
- The season-stats endpoint has a "defense" section that mixes pitching and fielding. What fielding-specific fields does it return?
- Does any endpoint return catcher-specific stats separately from general fielding?
- Does any endpoint return pitch type breakdowns (fastball %, curve %, etc.)?

## Notes
- E-100 Non-Goal: "Fielding, catcher, and pitch type tables: Deferred. Purely additive (no FK references from other tables), doesn't block anything."
- E-100 Technical Notes: "Fielding/catcher/pitch type tables deferred (purely additive, no FK deps)."
- The glossary (`docs/gamechanger-stat-glossary.md`) includes fielding and catcher stat definitions.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
