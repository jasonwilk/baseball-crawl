# IDEA-031: Stat Blending Logic

## Status
`CANDIDATE`

## Summary
Implement loaders that merge API season stats with boxscore-derived stats. E-100 created the provenance columns (`stat_completeness` with three states: full/supplemented/boxscore_only, plus `games_tracked` on season tables) but deferred the blending strategy.

## Why It Matters
For member teams, the season-stats API endpoint provides authoritative aggregate stats. For opponents (scouted via boxscores), season stats are derived from whatever games we've crawled — potentially incomplete. Blending logic decides: when we have both API stats and boxscore-derived stats for the same player-season, which values win? How do we track confidence? This is critical for accurate scouting reports.

## Rough Timing
After IDEA-028 (base stat population) ships and both member and opponent data are flowing. Promote when:
- Both season-stats loader and scouting loader are populating full stat columns
- Coaches need to compare member stats (API-sourced) with opponent stats (boxscore-derived) and want confidence indicators

## Dependencies & Blockers
- [ ] IDEA-028 (base stat population) — both API and boxscore paths must be populated first
- [ ] Scouting pipeline must be producing opponent season stats from boxscores

## Open Questions
- When API season stats and boxscore-derived stats conflict, which wins? (Likely: API is canonical, boxscore supplements gaps.)
- Should `supplemented` mean "API base + boxscore fill-in" or "boxscore base + API override"?
- How does `games_tracked` interact with the API season stats? (API stats cover all games the player played, not just the ones we tracked.)
- Should the dashboard display provenance indicators (e.g., "based on 12 of 28 games") to coaches?

## Notes
- E-100 Non-Goal: "Stat blending logic: Loaders that merge API season stats with boxscore-derived stats are follow-up scope. E-100 creates the provenance columns; population strategy is deferred."
- Baseball-coach consultation recommended: what level of stat confidence do coaches need to see?
- Related to IDEA-028 (stat population) but architecturally distinct — this is about merge strategy, not field mapping.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
