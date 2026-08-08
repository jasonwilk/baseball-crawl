# IDEA-067: Catcher-Pitcher Restriction (NSAA)

## Status
`CANDIDATE`

## Summary
Implement the NSAA catcher-pitcher restriction in the availability engine: a player who has caught 4 or more innings in a game may not pitch in that same game. This is a real NSAA rule that coaches navigate but is not currently tracked by the starter prediction engine.

## Why It Matters
The catcher-pitcher restriction is a compliance rule (like pitch count rest tiers). A predicted starter assessment that doesn't account for it could suggest a pitcher who is actually ineligible because he caught the first 4 innings. This is most relevant for small rosters where players serve dual roles (catcher/pitcher).

## Rough Timing
After E-217 is complete. Low urgency -- the restriction applies within a single game (not across games), so it primarily affects in-game bullpen decisions rather than pre-game starter predictions. The starter prediction engine predicts who starts, not who relieves mid-game.

## Dependencies & Blockers
- [x] E-217 (NSAA pitch rules) must be complete
- [ ] Catching innings data must be available (defensive position + innings from boxscore or plays data)
- [ ] Need to verify if NSAA has reciprocal restriction (pitcher → catcher limit)

## Open Questions
- Does the boxscore data include per-player defensive innings (specifically innings caught)?
- Is the restriction enforced per-game only, or does it carry across doubleheader games?
- Does NSAA have a reciprocal restriction (pitcher who threw X pitches cannot catch)?

## Notes
- Identified during E-217 domain consultation with baseball-coach
- This is a within-game restriction, unlike pitch count rest tiers (across games). Different enforcement scope.
- May be more relevant for a future "in-game availability" feature than for pre-game starter prediction

---
Created: 2026-04-07
Last reviewed: 2026-04-07
Review by: 2026-07-06
