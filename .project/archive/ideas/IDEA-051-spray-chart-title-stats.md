# IDEA-051: Title with Stats on Spray Charts

## Status
`CANDIDATE`

## Summary
Enhance spray chart titles to include key stats alongside the player name -- e.g., "John Smith -- .345 BA | 47 BIP | 52% Pull" -- so the chart is self-documenting for scouting sheets and exports.

## Why It Matters
When spray charts are viewed in a scouting report or shared as standalone images, the current title (player name only) lacks context. Adding a stat line makes each chart interpretable without cross-referencing a separate stats table. This is especially important if charts are printed, screenshotted, or embedded in pre-game prep materials where the surrounding dashboard context is not available.

## Rough Timing
- After spray chart rendering is stable and stats are reliably populated
- Relatively simple enhancement -- could ship alongside IDEA-049 (pull/center/oppo) since that summary data would feed into the title

## Dependencies & Blockers
- [x] Spray chart pipeline operational (E-158)
- [x] Spray chart rendering in `src/charts/spray.py` exists
- [ ] Season batting stats populated (BA or OBP available per player) -- E-117 complete
- [ ] Pull/center/oppo computation available if pull% is desired in title (see IDEA-049)

## Open Questions
- Which stats belong in the title? BA and BIP count are obvious. Pull% requires IDEA-049 logic. OBP? SLG?
- How much fits before the title becomes cluttered? Need to balance information density with readability.
- Should team-aggregate charts have a different title format than per-player charts?
- Font sizing and layout -- does a multi-stat subtitle fit cleanly in the current chart dimensions?

## Notes
- Related: IDEA-048 (fielder zones), IDEA-049 (pull/center/oppo), IDEA-050 (hot-cold zones)
- BIP count is trivially available from the spray data itself (count of rows)
- BA/OBP requires joining to season_batting stats
- Natural pairing with IDEA-049 since pull% is a likely title stat

---
Created: 2026-03-27
Last reviewed: 2026-03-27
Review by: 2026-06-25
