# IDEA-221: The same number is formatted by several independent render paths, and they disagree

## Status
`CANDIDATE` — **live on production AND dev, identically. Coach-facing. Four observed symptoms; at least three share one likely root.**

## Summary

Four cross-section inconsistencies were found on a generated report, **present identically in live and dev** — so these are render-path defects in code, not data or environment differences. Three of the four are the same shape: **one value, several formatting paths, no shared seam.**

| # | symptom | the tell |
|---|---|---|
| 1 | The **Top Bat key-player callout** shows a SLG one digit below the batting table and the spray card, which agree with each other (`.537` vs `.538`) | two agree, one differs — **the callout render path is the outlier** |
| 2 | A **Most Likely Arms mini-log row** shows an **illegal innings-pitched value of `5.3`**, where the main pitching table shows `5.1` for the same outing | thirds only go `.0` / `.1` / `.2`; `5.3` cannot be a real IP |
| 3 | A batter at **exactly `.2625`** renders `.263` in the batting table and `.262` on his spray card | a value sitting precisely on a rounding boundary, resolved two ways |
| 4 | The **bullpen annotation's `N/29` numerators** do not match the pitchers' GR counts in the pitching table, and the `/29` denominator is unexplained | **lower confidence — flagged for investigation, not asserted as a defect** |

## Why It Matters

**Symptom 2 is the one that matters most, and it is qualitatively different from the others.** `5.3` innings pitched is not a rounding disagreement — **it is not a value that can exist.** Innings are stored as integer outs (`ip_outs`, 1 IP = 3 outs) and rendered in thirds, so the fractional digit is only ever `.0`, `.1` or `.2`. A coach who notices it learns that a number on this card was computed by something that does not know what an inning is; a coach who does not notice reads a workload figure that is wrong by a third of an inning in an unknown direction. It appears on the **Most Likely Arms** card, which exists to inform pitcher-availability decisions.

The others are individually cosmetic — a coach is not making a different decision on `.537` versus `.538`. **Their cost is cumulative and is about trust rather than accuracy**: the report's whole proposition is that a coach can stop cross-checking GameChanger by hand. Two numbers for one player on one page invites exactly the cross-checking the tool exists to replace, and it invites it under pre-game time pressure. `.claude/rules/data-model.md` already states the project's position for game counts — *one honest count and one honest date everywhere* — and the same logic reaches per-player rate stats.

**The structural reading is the reusable one.** Three separate sections formatting the same underlying value three ways is the canonical-seams defect (`CLAUDE.md`: adding a second path to something that already has one is the recurring defect here; the copies drift, and the one nobody updated is the one that runs) showing up in the **presentation** layer instead of the data layer. Fixing four symptoms individually leaves the fifth to be found by a coach.

## Rough Timing

**Fold into the next epic touching the report template or renderer**, with symptom 2 promotable on its own if the operator wants the illegal IP value gone sooner — it is the only one with a plausible coaching consequence.

Do not defer symptom 2 to a general formatting cleanup that may not happen for months.

## Dependencies & Blockers
- [ ] None. All four are reproducible from an existing generated report.

## Open Questions

Hypotheses below are **from reasoning about the observed values, not from reading the render paths.** They are starting points to falsify, not diagnoses — check the code before acting on any of them.

- **Is symptom 2 a decimal division where a thirds conversion belongs?** `16` outs is `5.1` in thirds and `5.333…` as a decimal, which formats to `5.3`. That would make it a wrong *unit conversion* rather than a rounding difference, and it would mean the mini-log path never had the thirds logic at all. If so, the same path may be wrong for every outing, with only the non-multiples of three visibly illegal.
- **Are symptoms 1 and 3 a round-half-even versus round-half-up split?** A value at exactly `.2625` is the classic discriminator: Python's `round()` and `%`-formatting use banker's rounding (`.262`), while a hand-rolled or template-filter rounding typically rounds half up (`.263`). If that is the split, the fix is choosing one convention and routing every rate stat through it — and **the choice should be ruled, not defaulted**, since coaches read stat lines against GameChanger's own conventions.
- **How many render paths format rate stats today?** Nobody has counted. That number decides whether this is a two-line fix or a small consolidation, and it is the first thing to establish.
- **What is the `/29` denominator in the bullpen annotation?** Unexplained, and the numerators disagree with the pitching table's GR counts. **Lowest confidence of the four** — it may be a legitimate figure over a population nobody documented, in which case the defect is that it is undocumented. Establish what the fraction is counting before calling it wrong.
- **Should a rate stat be formatted once at query time rather than per-section at render time?** Would make divergence structurally impossible, but pushes presentation into the data layer. A ux-designer and SE call together, not a PM one.

## Notes

Found in the four-agent live-vs-dev report evaluation on 2026-07-26/27 (render-evaluation lane). **The live/dev identity is the load-bearing fact**: both environments render the same wrong values from independently loaded data, which rules out data corruption and localizes all four to the render paths.

Companion result from the same evaluation, recorded so it is not re-investigated: the calc lane verified ~314 facts per environment as computationally correct with identical behaviour across prod and dev, and ruled 3 P/BF cells consistent with charted-PA gating as **verified-NOT-defect** ([[IDEA-196]] carries that in full). **So the computation is sound and the divergence is in presentation** — that is what makes this a formatting-seam problem rather than a stats problem, and it is the single most useful thing this capture carries.

**⛔ No player is identified in this file, deliberately** — the affected batters and pitchers are described by their stat values only.

Symptom 4 is kept in this file rather than split out because it was found in the same pass on the same card family and may share a root; if investigation shows it is a documentation gap rather than a formatting divergence, split it then.

Related: [[IDEA-217]] (record-header divergence from the same evaluation — a *query*-layer instance of the same "two surfaces, two answers" shape), [[IDEA-196]], [[IDEA-083]], [[IDEA-076]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
