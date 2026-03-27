# IDEA-048: Fielder Position Labels/Zones on Spray Charts

## Status
`CANDIDATE`

## Summary
Show defensive position labels or zone overlays on spray chart images so coaches can see at a glance where balls are being fielded relative to standard defensive positions.

## Why It Matters
Spray charts currently show raw ball-in-play coordinates without positional context. Adding fielder position labels (1B, SS, CF, etc.) or zone boundaries gives coaches an immediate frame of reference for interpreting hit distribution. A coach preparing defensive positioning can see "most balls go to the SS zone" without mentally mapping coordinates to positions.

## Rough Timing
- After spray chart rendering is stable and in regular coaching use
- Low urgency -- the current charts are functional, this is a usability enhancement

## Dependencies & Blockers
- [x] Spray chart pipeline operational (E-158)
- [x] Spray chart rendering in `src/charts/spray.py` exists
- [ ] Coaches actively using spray charts and requesting positional context

## Open Questions
- Should positions be labeled text (e.g., "SS", "CF") or zone shading or both?
- Where do the zone boundaries fall? Standard MLB positioning, or derived from actual fielder data if available?
- Does the spray chart coordinate system map cleanly to standard field geometry for zone placement?

## Notes
- Related: IDEA-049 (pull/center/oppo), IDEA-050 (hot-cold zones), IDEA-051 (title stats)
- Current renderer is in `src/charts/spray.py` using matplotlib + numpy
- Spray data stored in `spray_charts` table with x/y coordinates, fielder position column already exists

---
Created: 2026-03-27
Last reviewed: 2026-03-27
Review by: 2026-06-25
