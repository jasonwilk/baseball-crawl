# IDEA-113: Rename or fold src/db/season_aggregates.py post-cutover (it no longer computes aggregates)

## Status
`CANDIDATE`

## Summary
After E-259's query-time cutover, `src/db/season_aggregates.py` no longer computes or writes season aggregates — the DELETE+INSERT recompute driver (`canonical_recompute`) is deleted, leaving only the projection SQL builders (`batting_recompute_select()`/`pitching_recompute_select()`) and the `*_RECOMPUTE_KEYS` tuples that a *reader* (`get_season_batting`/`get_season_pitching` in `src/api/db.py`) consumes. The module name and the `*_recompute_*` symbol names become a mild misnomer. Rename the module (and/or the symbols) or fold the surviving projection helpers into `src/api/db.py` next to their sole consumer.

## Why It Matters
A module named `season_aggregates.py` whose only remaining job is to hand a reader a SUM projection is a small but real orientation trap for future work — someone looking for "where season aggregates are computed" will open it and find a projection helper, not a compute path. Co-locating the projection with its sole consumer (the query-time reader) also tightens the "exactly one SUM projection" invariant E-259 establishes.

## Rough Timing
Promote as a small tidiness follow-up after E-259 lands and the cutover has soaked. No urgency — purely cosmetic/orientation; the code is correct as-is.

## Dependencies & Blockers
- [ ] E-259 must complete first (the misnomer only exists post-cutover).

## Open Questions
- Rename the module in place (`season_projection.py`?) vs. fold the builders + KEYS tuples into `src/api/db.py`?
- Do the `*_recompute_*` symbol names get renamed too, or kept for git-blame continuity?
- Does anything else import from `season_aggregates.py` after E-259-02 that would widen the blast radius?

## Notes
Surfaced by data-engineer during the E-259 holistic review (2026-07-09). Out of E-259 scope (E-259 retains the builders deliberately so exactly one SUM projection survives; renaming would enlarge the cutover diff). Domain: data-engineer. Anchors: `src/db/season_aggregates.py`, `src/api/db.py` (`get_season_batting`/`get_season_pitching` after E-259-01).

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
