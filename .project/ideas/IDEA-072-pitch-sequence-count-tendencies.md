# IDEA-072: Pitch Sequence / Count-Based Tendencies

## Status
`CANDIDATE`

## Summary
Surface per-pitcher sequencing patterns from plays data — e.g., "After going 0-1, pitcher X throws a breaking ball 60% of the time." Gives LSB batters a predictive edge on what to expect in specific count situations.

## Why It Matters
Knowing what a pitcher throws when ahead or behind in the count is one of the highest-value pre-game preparation tools in baseball. At the HS level, most pitchers have limited repertoire and clear tendencies. A batter who knows "he goes fastball 2-0, breaking ball 0-2" can sit on pitches rather than react. We have plays data — the compute is the only gap.

## Rough Timing
After plays data pipeline has sufficient game coverage (10+ games per pitcher for meaningful pattern detection). Likely a follow-on epic after matchup v1 ships and coaches are regularly using the scouting report.

## Dependencies & Blockers
- [ ] Plays data pipeline must be stable and have high game coverage (not just sporadic)
- [ ] Per-pitch sequence data must be reliably populated in plays table (verify coverage before building)
- [ ] Compute cost for sequence aggregation needs a feasibility spike — may require materialized views or pre-aggregation

## Open Questions
- What is the minimum pitch sample per count-state to surface a tendency? (Suggest 10+ pitches in a given count before showing a pattern)
- Do we aggregate at pitcher level only, or also at team level ("Westside's staff goes fastball 70% on 0-0")?
- How do we handle multi-pitcher game appearances (only the starter, or all arms)?

## Notes
Flagged in 2026-04-27 coach brainstorm during matchup epic discovery. Coach noted this is "interesting if cheap" — the coaching value is high but compute cost and plays coverage are real blockers. Recommend a research spike before planning this as an epic. Related to IDEA-041 (play-by-play stat compilation pipeline).

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
