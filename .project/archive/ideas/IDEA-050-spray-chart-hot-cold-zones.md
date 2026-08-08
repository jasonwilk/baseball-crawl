# IDEA-050: Count Overlay / Hot-Cold Zones on Spray Charts

## Status
`CANDIDATE`

## Summary
Show heat-map style hot/cold zones on spray charts based on density of balls in play, giving coaches a visual representation of where a batter most frequently puts the ball.

## Why It Matters
Individual dots on a spray chart become hard to interpret at scale (30+ BIP). A heat map or density overlay highlights clusters and cold spots that are not obvious from scattered points. This is especially valuable for team-aggregate spray charts where hundreds of BIP make individual dots meaningless. Coaches can spot "this batter hammers the left-center gap" at a glance.

## Rough Timing
- After spray charts are in active coaching use with enough data to make density meaningful
- More complex than text overlays -- probably a later enhancement
- Most valuable for team-level aggregates (high BIP count) rather than per-player charts

## Dependencies & Blockers
- [x] Spray chart pipeline operational (E-158)
- [x] Spray chart rendering in `src/charts/spray.py` exists
- [ ] Sufficient BIP data loaded to make density meaningful (display threshold: 20 BIP for team, 10 for player)
- [ ] matplotlib supports the rendering approach (contour, hexbin, or KDE)

## Open Questions
- Which visualization technique? Options: matplotlib hexbin, KDE contour, gaussian smoothing, or discrete grid cells with color fill
- Should the heat map replace the individual dots or overlay on top of them?
- Color scale: diverging (hot-cold) or sequential (density gradient)?
- Does this work well at the per-player level with only 10-30 BIP, or is it only meaningful for team aggregates?

## Notes
- Related: IDEA-048 (fielder zones), IDEA-049 (pull/center/oppo), IDEA-051 (title stats)
- matplotlib has built-in hexbin and KDE support via numpy, both already in the dependency chain
- May want to offer both "dots" and "heat" rendering modes rather than replacing the current view

---
Created: 2026-03-27
Last reviewed: 2026-03-27
Review by: 2026-06-25
