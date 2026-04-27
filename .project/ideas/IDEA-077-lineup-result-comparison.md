# IDEA-077: Lineup Result Comparison (A/B Lineup View)

## Status
`CANDIDATE`

## Summary
Show LSB's offensive outcomes when using different lineup configurations — e.g., "When Froeschl batted leadoff for 5 games: .350 team OBP, 4.2 R/game. When Foster batted leadoff for 4 games: .310 team OBP, 3.1 R/game." Mandatory small-sample caveat on all comparisons.

## Why It Matters
Coaches who experiment with lineup order have no way to evaluate the results systematically. The data to answer "did that change work?" is in the system; the surface does not exist. Even with heavy small-sample caveats, a 5-game comparison is better evidence than gut feel for a coaching staff making decisions week to week.

## Rough Timing
After LSB has accumulated enough games to make any comparison meaningful (15+ games minimum for two lineup configs to have 5+ games each). Mid-season or end-of-season review feature. Not a game-day tool.

## Dependencies & Blockers
- [ ] Per-game batting order data must be captured and stored (verify this is currently populated)
- [ ] Need lineup configuration grouping logic — how to define "same lineup" across multiple games
- [ ] Small-sample caveat display must be prominent and mandatory (PA count per configuration required)

## Open Questions
- How do we define a "lineup configuration" — exact same order, or same top-3 batters?
- Is this a coach-driven query ("compare these two periods") or an automatic detection ("we detected a lineup change on date X")?
- Should this include only batting order, or also starting pitcher pairings?

## Notes
Flagged in 2026-04-27 coach brainstorm as "useful." Coach framed it as "we tried lineup X for 3 games, lineup Y for 3, here's the diff" — suggesting the primary use case is evaluating deliberate experiments, not automated change detection. Small-sample caveat is mandatory per our display philosophy — do not suppress, always contextualize with game/PA counts.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
