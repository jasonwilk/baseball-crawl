# IDEA-087: Multi-Pitcher-Boundary Attribution Drift (cause-4)

## Status
`CANDIDATE`

## Summary
In some multi-pitcher games, the plays-derived pitcher attribution mis-assigns plate appearances at
the boundary between pitchers, over-crediting one arm. The clearest example is game `e283438c`
(perspective 100): one pitcher is credited 22 plays vs. the boxscore's 11 — a +23 BF outlier — and
this is NOT a self-game (home=220, away=100) and NOT play duplication (60 plays / 60 distinct
orders), but a within-game pitcher-boundary mis-assignment. This is "cause-4" in DE's E-245
reconciliation baseline.

## Why It Matters
Pitcher workload and per-pitcher rate stats (BF, pitch counts, FPS%) depend on correct
play→pitcher attribution. A boundary mis-assignment inflates one arm and deflates another, which
distorts the workload view and any per-pitcher scouting line. The reconciliation engine already
corrects pitcher attribution using boxscore BF as ground truth, so this is likely a gap or edge case
in that corrector rather than a missing capability.

## Rough Timing
After E-245 (which scoped this out deliberately to stay focused on the pitch-detail-drop and
self-game axes). Promote when the residual attribution drift is measured to be material, or when a
coach is misled by an inflated pitcher line.

## Dependencies & Blockers
- [ ] E-245 complete (self-game axis closed first, so the measurement isn't confounded by
      `home == away` collapse)
- [ ] DE quantifies the residual boundary-drift magnitude across the season (how many games, how
      large the deltas) to decide if it's worth an epic

## Open Questions
- Is this a gap in the reconciliation engine's BF-boundary corrector (`src/reconciliation/engine.py`)
  or upstream in how the parser assigns `pitcher_id` across substitution boundaries?
- How common and how large is the drift season-wide once self-games are removed? (DE baseline noted
  pitching BF fidelity drift of ~44 units, mostly ±1, plus a few larger over-attributions.)
- Does fixing it require boxscore appearance-order ground truth the engine already reads, or new
  signal?

## Notes
- Source: DE's E-245 reconciliation baseline (`.project/research/E-245-plays-boxscore-reconciliation-baseline.md`),
  "Ranked dominant causes" #4 (pitcher-attribution / multi-pitcher boundary drift).
- Scoped OUT of E-245 explicitly (epic Non-Goals) to avoid the self-game fix claiming to address it.
- Related: the reconciliation engine already measures/corrects pitcher attribution against boxscore
  BF (`.claude/rules/architecture-subsystems.md`, Reconciliation Package).

---
Created: 2026-06-29
Last reviewed: 2026-06-29
Review by: 2026-09-27
