# IDEA-141: Pitcher-outings epic must own the K-rate stat/basis decision

## Status
`PROMOTED` — folded into E-265 (Pitcher Outings Breakdown) as Open Question #1; RESOLVED at E-265 refinement 2026-07-15.

## Summary
The upcoming pitcher-outings epic (redesigning the pitching-stat presentation) must explicitly pick up the deliberate, holistic decision of which strikeout-rate stat(s) to show and on what basis — K/9 vs K/G vs K/BF vs K/BB — so that decision is not dropped in the gap between E-264 (ERA-basis fix) and that epic.

## Why It Matters
E-264 deliberately scoped ERA-only and left the report's K/9 exactly as-is (our own `SO × 27 / outs`, traditional 9-inning, NOT a GameChanger-displayed stat). baseball-coach confirmed this is correct for E-264 — coaches benchmark traditional K/9 against external recruiting standards, so a piecemeal rebase riding on the ERA fix would mislead. But GameChanger itself shows K/G (game-length basis, `innings_per_game × SO / IP`), K/BF, K/BB, and BB/INN — not K/9. The right place to reconcile our K-rate presentation with GC's (and to decide whether to keep, replace, or add to K/9) is the pitcher-outings epic, which is already redesigning the pitching stat set. If that epic's scope doesn't name this explicitly, the decision falls through the cracks and the report keeps an un-reconciled invented stat indefinitely.

## Rough Timing
When the pitcher-outings epic is planned. This is a scope-inclusion reminder, not standalone work — fold it into that epic's Open Questions / scope, don't build it separately.

## Dependencies & Blockers
- [ ] The pitcher-outings epic is planned (this idea is a scope note to attach to it)
- [ ] E-264 (ERA-basis fix) is the immediate precedent establishing the innings_per_game basis in the codebase (`teams.innings_per_game`), which the K/G option would reuse

## Open Questions
- Keep traditional K/9, replace it with GC's K/G, or show both with clear labels?
- Which of GC's rate stats (K/BF, K/BB, BB/INN, BAA) belong on the redesigned pitcher surface? (baseball-coach's prior consultation had "K/9 or K%" as MUST-HAVE and K/BB as SHOULD-HAVE — see `.claude/agent-memory/baseball-coach/pitcher-outings-scouting-consultation.md`.)
- If K/G is added, it reuses `teams.innings_per_game` (from E-264) — no new fetch needed.

## Notes
Raised by baseball-coach during E-264 formation (2026-07-15). Related: E-264 (ERA-basis fix, its Non-Goals defer this) and the `teams.innings_per_game` basis E-264 introduces. **RESOLVED at E-265 refinement (2026-07-15):** baseball-coach ruled the new Outings Breakdown's K-rate set = **K/BF + BB/INN + K/BB** — drop BOTH the invented K/9 AND GC's K/G on this section. Rationale: it is a brand-new surface with no legacy number to protect (so the "coaches expect traditional K/9" argument that kept E-264 from touching the existing pitching-table K/9 does NOT transfer here), and K/BF sidesteps the innings-per-game basis question entirely — no per-team asterisk/footnote machinery like E-264's ERA disclosure. K/BF (miss-bats rate, BF denominator) is also more tactically honest for prepping to face the arm, independent of choppy HS relief IP; BB/INN is GC's real per-inning field; K/BB shares its numerator with K/BF. The existing pitching-table K/9 (a different surface) is unchanged. Decision recorded in E-265 epic Resolved Decisions.

---
Created: 2026-07-15
Last reviewed: 2026-07-15
Review by: 2026-10-13
