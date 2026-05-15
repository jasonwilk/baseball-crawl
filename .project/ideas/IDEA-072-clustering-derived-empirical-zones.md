# IDEA-072: Clustering-Derived Empirical Fielding Zones

## Status
`CANDIDATE`

## Summary
The planned fast-follow to E-228's fixed-geometry positioning engine: instead of hardcoded angular sectors, *derive* the fielding zones empirically -- cluster each opponent lineup's per-batter optimal fielding points into 2-3 discovered zones per position. E-228 ships fixed angular-sector geometry behind a deliberately swappable seam; this idea swaps the geometry component for a clustering-derived one.

## Why It Matters
Fixed angular sectors are a reasonable starting approximation but they are a guess about field geometry, not a measurement. Clustering the actual per-batter optimal points (which E-228's engine already computes -- TN-3 Stage A) discovers where opposing hitters' tendencies actually concentrate, per lineup. Higher ceiling than fixed geometry: the zones reflect the real data rather than a coach's mental model of "left field / center / right field." E-228 was explicitly architected so this is a one-layer swap, not an engine rewrite -- the engine's `direction_shade` / `call_state` output shape is identical whether zones come from fixed sectors or clustering.

## Rough Timing
After E-228 ships and its first-real-opponent design-time calibration pass runs. The calibration pass has an explicit second job: assess whether the per-batter optimal-point centroids are tight enough to justify clustering. That assessment is the trigger -- promote this idea if the calibration pass confirms centroid tightness; hold it if it does not.

## Dependencies & Blockers
- [ ] E-228 (Defensive Positioning Pocket Cards) complete -- it builds the per-batter optimal-point computation and the swappable geometry seam this idea plugs into.
- [ ] E-228's design-time calibration pass run, and it confirms per-batter centroids are tight enough to cluster meaningfully (the signal-to-noise gate -- see below).

## Open Questions
- The signal-to-noise gate: at 15-35 BIP per batter, each per-batter optimal point carries large sampling error, and clustering ~10-13 such points per lineup risks overfitting noise. Does the real-opponent calibration data show the centroids are tight enough? (This is the gate, not a side question.)
- Guard-rails the clustering needs: fixed `k` (not a free `k`), a min-separation collapse rule (if two clusters are too close, merge them), and BIP-weighting (a 35-BIP batter's point should count more than a 15-BIP batter's). What are the starting values?
- Does clustering run per-opponent-lineup at recompute time, or is it a periodic batch step? (Per-lineup is more responsive but re-solves the clustering every scouting run.)
- This is a bigger story than E-228-02 was -- does it need a research spike first to validate the clustering approach against real data before it can be specced with concrete ACs?

## Notes
- Origin: raised by the user during E-228 planning as "derive the zones instead of hardcoding them." The math-for-runtime half of the idea (compute the optimal point) was pulled into E-228-02 directly; the clustering half was deferred to this idea, gated on signal-to-noise.
- The reason this is NOT in E-228 v1 is signal-to-noise, NOT stability -- data-driven change between runs is a feature, not a defect. The only question is whether the per-batter inputs are precise enough to cluster.
- data-engineer's read during E-228 planning: viable, higher ceiling than fixed geometry, but a bigger story.
- Related: IDEA-073 (team-wide base alignment) -- a different aggregation of the same spray data.

---
Created: 2026-05-15
Last reviewed: 2026-05-15
Review by: 2026-08-13
