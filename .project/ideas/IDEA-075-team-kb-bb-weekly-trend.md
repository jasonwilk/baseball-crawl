# IDEA-075: Team K% and BB% Weekly Trend Dashboard Card

## Status
`CANDIDATE`

## Summary
A dashboard card showing LSB's team-level K% (as batters) and BB% (allowed by pitchers) trended week-over-week across the season. Identifies whether practice adjustments are working or whether problems are compounding over time.

## Why It Matters
Season-aggregate stats hide direction. A team with a .280 K% in March that is now .340 K% in May has a worsening problem — the season average masks it. Week-over-week trending surfaces this signal and connects directly to practice priorities ("we are striking out more in May — drill two-strike approaches"). We have game-by-game data; this is a rolling aggregation over time.

## Rough Timing
After LSB team data is populated for a full season (at least 10+ games to make the trend meaningful). Natural fit for a mid-season dashboard review feature. No opponent data required — this is purely own-team analysis.

## Dependencies & Blockers
- [ ] Per-game batting outcomes (K, BB, PA) must be reliably populated for LSB
- [ ] Dashboard must have a time-series visualization capability (or this drives adding one)

## Open Questions
- Weekly buckets or rolling 7-day windows? Weekly buckets are simpler and more intuitive for coaches who think in game weeks.
- Show absolute K% per week, or delta vs season baseline?
- Combine batting K% and pitching BB/9 on one card, or separate cards?

## Notes
Flagged in 2026-04-27 coach brainstorm as "must have someday." Coach framed it as a practice-prioritization tool — "we hit poorly in 0-2 counts as a team, drill that." The weekly trend is the mechanism that surfaces those patterns. This is a 5-minute dashboard card conceptually; the main investment is time-series data display.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
