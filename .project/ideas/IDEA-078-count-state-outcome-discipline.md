# IDEA-078: Count-State Outcome Discipline (0-2 K% and Ahead/Behind Split)

## Status
`CANDIDATE`

## Summary
Surface LSB's team-level outcome rates by count state — specifically K% when the pitcher is ahead (0-2, 1-2) vs. behind (2-0, 3-1) in the count, for both pitching (are we putting hitters away?) and batting (are we protecting with two strikes?). Maps directly to practice priorities.

## Why It Matters
"We get to 0-2 often but our K rate does not reflect it" is a discoverable pattern that drives a specific practice intervention: "work on put-away pitches." The inverse ("our batters are getting to 2-0 but not capitalizing") drives a different drill. Count-state breakdowns are common in pro analytics and entirely achievable from plays data at the HS level. The question answers itself — if the data shows a gap, the practice focus is obvious.

## Rough Timing
After plays data pipeline has sufficient game coverage for LSB (10+ games). Likely a v2 feature after basic own-team dashboard cards are in place. Requires plays data; not available from boxscore alone.

## Dependencies & Blockers
- [ ] Plays data must be populated for LSB games with reliable count-state tagging
- [ ] Per-pitch count-state fields must be present in plays table
- [ ] Sufficient game coverage (10+ games) for the aggregations to be meaningful

## Open Questions
- Which count states to surface? Full matrix (all 12 counts) or a simplified ahead/even/behind summary?
- Separate pitching and batting views, or one combined card?
- Is this a coach-facing dashboard card or part of a practice-planning report?

## Notes
Flagged in 2026-04-27 coach brainstorm as "useful." Coach framed the primary use case as practice-time prioritization — "we hit poorly in 0-2 counts as a team, drill that." This is a plays-data feature; boxscore data alone cannot support it. Prioritize after plays coverage is verified to be sufficient for LSB games.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
