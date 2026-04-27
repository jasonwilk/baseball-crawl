# IDEA-073: Pitcher Fatigue Proxy — In-Game Pitch Count Reference Card

## Status
`CANDIDATE`

## Summary
Display a bench-ready reference card showing the LSB starter's last 3 game exit points (pitch count at exit) alongside the current game's running pitch count. Helps coaches make mid-game pull decisions using the pitcher's own historical fatigue curve, not a generic threshold.

## Why It Matters
Coaches currently pull pitchers based on feel and compliance thresholds (NSAA limits). A reference like "Von Seggern's last 3 outings: exited at 90P, 82P, 88P — currently at 68P" gives the coach a personalized floor estimate, not just a hard ceiling. This is a safety and performance tool simultaneously. We already have all pitch count data from game logs — this is a display problem, not a data problem.

## Rough Timing
Could ship as part of matchup report v2 (LSB-coupled content). Alternatively, could be a standalone dashboard card on the team pitching page. Low engineering lift once the matchup report knows "our team."

## Dependencies & Blockers
- [ ] Matchup report must have access to LSB team context (the two-team architectural lift from matchup epic discovery)
- [ ] Pitch count data per game per pitcher must be reliably populated (verify before building)

## Open Questions
- Should this be on the matchup report only, or also on the LSB team pitching dashboard?
- How many prior outings to show — last 3, last 5, or season range?
- Should the card auto-flag when current pitch count exceeds the pitcher's personal average exit point?

## Notes
Flagged in 2026-04-27 coach brainstorm as "must have someday." Coach described it as a bench card between innings — mobile-friendly, two-line reference. Not predictive modeling; purely historical reference. Engineering cost is low once LSB team context is available in the report flow.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
