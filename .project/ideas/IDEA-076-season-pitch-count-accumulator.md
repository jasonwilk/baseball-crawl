# IDEA-076: Individual Pitcher Season Pitch Count Accumulator

## Status
`CANDIDATE`

## Summary
A table showing each LSB pitcher's cumulative pitch count across the season — total pitches thrown, number of appearances, and a per-week breakdown. Arm health is a cumulative problem, not a per-game problem; this surfaces the full picture.

## Why It Matters
NSAA per-game limits protect pitchers game-to-game, but they do not capture cumulative workload across a 30-game season. A pitcher who throws 85 pitches every 4 days is in a different situation than one who throws 85 pitches once a week. Coaches who track this manually are rare. We have every pitch count from every game — this table is essentially free to build. It also directly supports arm health safety flags (bubble up: "Hiatt has thrown 412 pitches in 14 appearances this month").

## Rough Timing
High priority — this is a safety feature, not just a performance feature. Could ship as a standalone dashboard card independent of the matchup report epic. No architectural dependencies beyond having LSB pitch count data populated.

## Dependencies & Blockers
- [ ] Per-game pitch count data must be reliably populated for LSB pitchers
- [ ] Need to decide granularity: total season only, or per-week breakdown too

## Open Questions
- Should the accumulator surface a flag when a pitcher exceeds a coach-configured seasonal pitch count threshold?
- Does this live on the team pitching page, or is it a standalone "arm health" view?
- Should it include all pitchers or only those with 2+ appearances (to filter out one-inning cameos)?

## Notes
Flagged in 2026-04-27 coach brainstorm as "must have someday." Coach emphasized this is a table, not analysis — "it protects kids." The cumulative view is the gap; per-game tracking already exists via NSAA rest math. This should be treated as a safety feature and prioritized accordingly.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
