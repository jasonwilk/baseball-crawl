# IDEA-079: Opponent Error Clustering by Position and Game Situation

## Status
`CANDIDATE`

## Summary
Surface opponent fielding error patterns by defensive position — e.g., "Westside makes 70% of their errors at SS, mostly on slow rollers." Per-position season error rates are achievable from boxscore data now; per-situation error clustering (inning, game score, count) requires play-by-play.

## Why It Matters
Baserunning strategy against a weak fielder in a late, close game is a real and repeatable coaching decision. A coach who knows the opponent's SS is error-prone will run aggressively to the right side, bunt toward short, and look for slow rollers to force plays. This intelligence is currently invisible in any standard scouting view. Even a simple per-position error rate from boxscores gives coaches more than they have today.

## Rough Timing
Two-phase approach: per-position error rate from boxscores can ship as part of or shortly after the matchup report v1. Per-situation clustering (inning, game state) is a plays-data feature that follows once plays coverage is sufficient. No single dependency — can ship in stages.

## Dependencies & Blockers
- [ ] Error data by position must be populated from boxscores (verify field coverage in current schema)
- [ ] For per-situation analysis: plays data must be populated with fielding event tagging
- [ ] Minimum sample threshold: suggest 5+ errors at a position before surfacing a tendency

## Open Questions
- Does our current boxscore schema capture errors by fielding position, or only total errors per game?
- Is per-position error rate sufficient for v1 coaching value, or does it need game-situation context to be actionable?
- How do we handle games where error position data is missing or ambiguous?

## Notes
Flagged in 2026-04-27 coach brainstorm as "interesting if cheap." Coach noted the per-position season error rate is achievable from existing data; the per-situation analysis (inning, score state) is a plays-data extension. Recommend a schema check before planning — if error-by-position is already in the boxscore data, this may be very cheap to surface.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
