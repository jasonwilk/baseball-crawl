# IDEA-074: Live In-Game Opponent Hitter Lookup

## Status
`CANDIDATE`

## Summary
Mobile-friendly quick-reference lookup for any opponent hitter during a live game — two-line summary (OBP, BA, K%, BB%, SB, tendency note) accessible without generating a full report. Designed for between-inning glances, not pre-game prep.

## Why It Matters
Pre-game reports cover the top 5-7 hitters. But late in a game, a coach may face a #8 hitter they have not studied, or a pinch hitter they did not anticipate. The system has the data — the gap is a fast, mobile-optimized access path. A full report is too heavy for a 90-second between-inning window.

## Rough Timing
After core scouting report is stable and coaches are using it regularly. This is a UX polish feature that amplifies an already-working scouting pipeline. No new data required.

## Dependencies & Blockers
- [ ] Opponent scouting pipeline must be fully operational (data populated for tracked opponents)
- [ ] Mobile-responsive UI must be in place (dashboard/report pages must work on phone)
- [ ] Player search or team roster lookup needs a fast path (not a full page load)

## Open Questions
- Entry point: search by player name, or browse opponent roster?
- Should this be a dedicated page or a modal/overlay on the existing opponent page?
- Does "live" mean real-time data sync during the game, or just fast access to pre-loaded data?

## Notes
Flagged in 2026-04-27 coach brainstorm as "interesting if cheap." Coach described it as "this kid, two lines, right now" — not a report, not analysis, just fast data access. Low data requirement; the investment is in UX and navigation, not backend.

---
Created: 2026-04-27
Last reviewed: 2026-04-27
Review by: 2026-07-27
