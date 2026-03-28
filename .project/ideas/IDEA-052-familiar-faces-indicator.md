# IDEA-052: Familiar Faces Indicator on Opponent Rosters

## Status
`CANDIDATE`

## Summary
Show a "familiar faces" indicator on opponent scouting pages when an opponent roster includes players the coach has seen before -- either from prior seasons on other teams or from earlier matchups this season. Coaches naturally track players they've faced; surfacing this digitally saves pre-game prep time.

## Why It Matters
Coaches already do this mentally: "We played against #12 when he was on the Legion team last summer." Automating this recognition across seasons and programs gives coaches a head start on scouting. It's especially valuable in multi-program contexts (HS + Legion + travel ball) where the same players rotate through different teams.

## Rough Timing
- After cross-team player identity is reliable (`athlete_profile_id` as stable anchor -- see E-104 probe)
- After E-172 ships (opponent scouting workflow must be functional first)
- Nice-to-have for coaches; not blocking any core workflow

## Dependencies & Blockers
- [ ] E-104 (athlete_profile_id probing) must confirm opponent player identity is accessible
- [ ] E-172 (opponent scouting workflow) must be complete so rosters are reliably loaded
- [ ] Cross-team player matching must be reliable enough to avoid false positives

## Open Questions
- What's the best visual indicator? Badge on player row? Separate "Familiar faces" section?
- Should it show where/when the coach last saw this player?
- How reliable is `athlete_profile_id` for cross-team matching? (E-104 will answer this)
- Should it distinguish "played against" vs "played for us" (e.g., a player who transferred)?

## Notes
- Suggested by baseball-coach during E-172 template walkthrough as a nice-to-have
- Depends on stable cross-team player identity, which is a known open question (see Vision doc and E-104)
- Related to IDEA-009 (per-player stats) and the longitudinal player tracking vision

---
Created: 2026-03-28
Last reviewed: 2026-03-28
Review by: 2026-06-26
