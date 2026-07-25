# IDEA-179: LIVE under-rest hazard — `Under 13` / `Over 18` / `NNO` fall through to adult pitch tables

## Status
`CANDIDATE` — **live defect. A baseball-coach ruling is pending (routed 2026-07-25); the defect exists regardless of how it is ruled.**

## Summary
GameChanger's create-team **recreational** family offers exactly three options — `Under 13`, `Between 13 - 18`, `Over 18` — and **only the middle one is parsed.** The travel family's `NNO` "and over" form (e.g. `18O`) is likewise unmatched. All fall through to team-name keyword matching:

```
rec    "Under 13"  + name containing "Reserve"  + summer  ->  nrbl (105 max)
rec    "Over 18"   + name containing "Reserve"  + summer  ->  nrbl (105 max)
travel "18O"       + name containing "Reserve"  + summer  ->  nrbl (105 max)
```

**A team whose coach explicitly declared "Under 13" can land on the 105-pitch Legion-equivalent table.**

## Mechanism (traced in code, not inferred)
- `_AGE_RANGE_RE = \b\d+\s*-\s*\d+\b` needs **digit-dash-digit**. `Under 13` and `Over 18` carry one number each → no match.
- `_AGE_BRACKET_RE = \b(\d+)U\b` requires a **`U`** suffix. `18O` and `middle_13O` use `O` → no match.
- With neither matching, `_league_from_age_bracket(age_group)` returns `None`, the range branch does not fire, and control reaches `_league_from_level_word(team_name, season)` where `\breserves?\b` → sub-varsity → summer → `nrbl`.

## Why It Matters
This is the **same mechanism** as the `middle_12U`/`elementary` suppression baseball-coach ruled on for E-274 — but on the **rec/travel families, which coach was never shown.** The suppression ruling should almost certainly extend; it has **not** been extended, and assuming it does on a pitch-count gate is exactly the inference not to make.

**It is LIVE, not prospective.** Unlike the school-family bracket hazard (which the `_` word-boundary quirk currently blocks), nothing blocks this one. It fires today for any young or adult rec team whose name happens to carry a level word.

**Severity, stated honestly in both directions.** Per baseball-coach's stakes correction, this gate governs **opponent-scouting predictions**, not LSB athlete safety or NSAA/ALB compliance — our own roster routes through the `teams.classification` DB field at Priority 1 and never reaches these paths. So the harm is a **wrong prediction about an opponent's availability**, not a 12-year-old being overworked by us. That is a real de-escalation. But the direction is the one this project treats as unacceptable, and unlike its school-family sibling this one is already firing.

## Rough Timing
Promote once baseball-coach rules. Natural to fix alongside [[IDEA-178]] — same function, same "unparsed form reaches the wrong table" family, and both are E-272-adjacent precedence/parsing defects rather than E-274 scope. **Do not fold into E-274**, which reads the *school* family only and neither creates nor fixes this.

## Dependencies & Blockers
- [ ] **baseball-coach ruling** (routed 2026-07-25): should `Under 13`, `Over 18`, and the `NNO` form suppress terminally, as `middle_*` / `elementary` / `college` do?

## Open Questions
- **`Under 13` and `Over 18` are opposite ends and may not want the same answer.** `Under 13` is the young hazard. `Over 18` is an adult rec league — arguably closer to Legion than to anything youth. A single "suppress the rec family" ruling would flatten that distinction; flag it rather than assume.
- **`18O` is travel-family, not rec.** Same unhandled mechanism, possibly a different right answer, and it sits next to a bracket ladder that already handles `18U` correctly.
- Does `middle_13O` (school family, `O` suffix) interact? It is already covered by E-274's school suppression **if** that ships — but it is unhandled today for the same `O`-suffix reason, so it is live on the name path meanwhile.
- Is the right shape a per-form allowlist, or a broader "an `age_group` that is non-empty but matched NO family must not fall through to a name-derived *adult* table"? The second is more robust against the next unhandled form but is a wider behaviour change.
- Are there real opponents in any of these states? Unmeasured. api-scout could size it, but note the vocabulary is now known **exhaustively from the UI**, so the set of unhandled forms is closed even though the population is not.

## Notes
Found by the operator supplying the exhaustive create-team vocabulary as screenshots of the real UI flow, and running **every possible value** through the classifier. Full vocabulary: 12 travel brackets (8U–18U plus `18O`), 3 rec ranges, 7 school values.

**This is the second defect in two days found only by exhaustive enumeration against ground truth** ([[IDEA-178]] was the first). Neither the test suite, the closure gates, nor the runtime smoke could have surfaced either: they assert that the pipeline runs and that known inputs resolve, never that the *input space* is covered. The durable lesson — **enumerate the vendor's actual vocabulary and run all of it, rather than testing the values we happen to have seen.**

Related: [[IDEA-178]] (companion E-272 precedence/parsing defect, same function), [[IDEA-171]] (promoted to E-274 — the school family only), E-274 TN-3 (the suppression ruling this one has NOT been extended to).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
