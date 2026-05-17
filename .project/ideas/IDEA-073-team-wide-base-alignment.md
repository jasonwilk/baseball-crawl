# IDEA-073: Team-Wide Base Defensive Alignment

## Summary
Aggregate a "base" defensive alignment for an opponent from their team-wide spray distribution -- a single team-level read ("this lineup hits the ball to the left side more than average") that sits above the per-batter positioning cards E-228 produces.

## Status
`PROMOTED` → E-229

## Why It Matters
E-228's positioning cards are per-batter -- one row per opposing hitter, one set of player cards keyed by jersey number. A team-wide base alignment is a different, coarser cut of the same data: before the at-bat-by-at-bat detail, what is this opponent's overall lean? It is a quick orienting fact for a coach scanning the call sheet -- "this is a left-side-heavy lineup overall." Moderate value: it does not change any per-batter recommendation, but it frames them.

## Rough Timing
Defer from E-228 v1. Revisit after E-228 ships and is in real coaching use -- if coaches ask for a team-level summary, promote it; if the per-batter cards prove sufficient on their own, it may not be needed.

## Dependencies & Blockers
- [ ] E-228 (Defensive Positioning Pocket Cards) complete -- this reuses E-228's spray aggregation and would surface on E-228's call sheet.

## Open Questions
- Where does it surface? All three E-228 planning experts agreed: at most a call-sheet header note. It does NOT get its own artifact and does NOT change the per-position player cards.
- Is "team-wide base alignment" computed the same way as a per-batter optimal point (just aggregated over all the lineup's BIP), or does it need a different method?
- Is this even worth a story, or is it a one-line addition folded into a future call-sheet revision?

## Notes
- Origin: raised during E-228 planning's math-vs-LLM convergence round. All three experts (data-engineer, software-engineer, baseball-coach): real concept, moderate value, defer from v1.
- Explicitly NOT in E-228 v1 scope -- E-228's value proposition is the per-batter recognition task; a team-wide summary is additive framing, not core.
- Related: IDEA-072 (clustering-derived empirical zones) -- a different aggregation of the same spray data.
- **Promoted to E-229 on 2026-05-16.** E-228's user dev validation surfaced that the textbook reference frame produced wrong defaults (STRAIGHT UP for every position on every opponent). E-229 reframes the whole positioning model around exactly this idea: a team-aggregate optimal position per (opponent, position), computed from the team-wide spray centroid, projected onto each fielder's textbook base (position-scaled). What was "additive framing" in IDEA-073 became the core reference frame in E-229.

---
Created: 2026-05-15
Promoted to E-229: 2026-05-16
Last reviewed: 2026-05-16
Review by: n/a (PROMOTED)
