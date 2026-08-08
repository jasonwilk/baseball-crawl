# IDEA-049: Pull/Center/Oppo Tendency Summary on Spray Charts

## Status
`CANDIDATE`

## Summary
Add a text summary to spray chart images showing directional tendency percentages (e.g., "Pull: 45% | Center: 30% | Oppo: 25%") so coaches can quickly assess a batter's hit distribution without counting dots.

## Why It Matters
Directional tendency is one of the most actionable pieces of scouting data for defensive positioning. A pull-heavy hitter warrants a shift; an oppo hitter does not. Currently coaches must eyeball the spray chart to estimate this. A computed summary removes guesswork and makes the chart self-contained for pre-game scouting sheets.

## Rough Timing
- After spray chart rendering is stable and in regular coaching use
- Could be an early enhancement since it is relatively simple to compute from existing x/y data

## Dependencies & Blockers
- [x] Spray chart pipeline operational (E-158)
- [x] Spray chart rendering in `src/charts/spray.py` exists
- [ ] Need to define pull/center/oppo zones (angle-based from batter handedness? fixed zones?)

## Open Questions
- How are pull/center/oppo defined? Typically angle-based relative to batter handedness (LHB vs RHB). Do we have batter handedness data reliably?
- If handedness is unknown, do we fall back to a fixed three-zone split?
- Where does the summary text appear on the image -- below the chart, in a legend box, or as a subtitle?

## Notes
- Related: IDEA-048 (fielder zones), IDEA-050 (hot-cold zones), IDEA-051 (title stats)
- Batter handedness (`bats` column on players table) is schema-ready but not yet populated (see IDEA-029)
- Could potentially derive handedness from spray distribution itself as a heuristic

---
Created: 2026-03-27
Last reviewed: 2026-03-27
Review by: 2026-06-25
