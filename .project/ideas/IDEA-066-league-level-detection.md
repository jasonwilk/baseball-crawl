# IDEA-066: League/Level Detection for Pitch Rules

## Status
`CANDIDATE`

## Summary
Automatically detect which league's pitch count rules apply to a given team (NSAA HS, American Legion, USSSA, Perfect Game) so the starter prediction engine can select the correct rule set without manual configuration. Sources: GC team metadata (may include classification), team name parsing ("Varsity"/"JV"/"Legion"/"14U"), `programs.program_type`, opponent name inference.

## Why It Matters
E-217 defaults all teams to NSAA varsity rules. This is correct for LSB's HS teams but wrong for Legion teams (different rest tiers, 105 max, same-day limit) and USSSA teams (innings-based, not pitch counts). As the platform expands to serve Legion and travel ball coaches, the predicted starter engine needs to apply the right rules automatically. Incorrect rules mean incorrect availability assessments -- a compliance failure that could mislead coaches.

## Rough Timing
After E-217 is complete. The trigger is when the first Legion or USSSA team is actively tracked and coaches are consuming predicted starter data for non-HS teams.

## Dependencies & Blockers
- [x] E-217 (NSAA pitch rules as data) must be complete -- provides the data structure
- [ ] At least one non-HS team actively tracked (Legion or USSSA)
- [ ] `programs.program_type` reliably populated for tracked teams

## Open Questions
- Does GC team metadata include a reliable league/level indicator, or do we need heuristic parsing?
- How do we handle opponent teams where we don't know the league? Default to the most permissive rules? Flag as "league unknown"?
- Do tournament-specific rules (Perfect Game) need special handling, or do we just apply the team's home league rules at all times?

## Notes
- Natural follow-on to E-217 (NSAA Pitch Count Availability Rules)
- The existing `programs.program_type` field (hs/usssa/legion) provides the primary mapping for owned teams
- For tracked opponents, the classification field and team name may be the only signals
- NSAA and Legion share the same data model (pitch count → rest days); adding Legion is a data change. USSSA requires structural engine extension (innings-based).

---
Created: 2026-04-07
Last reviewed: 2026-04-07
Review by: 2026-07-06
