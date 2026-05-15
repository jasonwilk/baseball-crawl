# IDEA-074: Borderline-Case Flag on the Positioning Call Sheet

## Status
`CANDIDATE`

## Summary
On the defensive positioning call sheet (E-228), surface a "this one is close" cue for the 1-2 batters per lineup whose tendency just barely clears the sample/concentration gate threshold -- a confidence signal that the shade call is real but thin, distinct from the existing `is_thin` (<10 BIP) tag.

## Why It Matters
baseball-coach raised this during E-228 iteration-2 input. A coach reading the call sheet treats every non-TRUE call with equal weight, but some shade calls clear the gate by a wide margin and some clear it by a hair. Flagging the marginal ones lets the coach apply judgement -- "the engine says shade left but it's borderline, watch the first AB and confirm." It is a trust/calibration aid, not a new positioning output.

## Rough Timing
After E-228 ships and the operator has run the first real-opponent calibration pass (the Rollout note in E-228's epic). The calibration pass will reveal whether the gate thresholds land in a place where "borderline" is a meaningful, common-enough category to be worth surfacing. Promote if the pain is real -- coaches asking "how confident is this call?" -- not before.

## Dependencies & Blockers
- [ ] E-228 (Defensive Positioning Pocket Cards) must be complete -- the call sheet, the Tier 1 engine, and the gate thresholds must exist.
- [ ] E-228's first-opponent calibration pass should be done, so the gate thresholds are stable enough to define "borderline" against.

## Open Questions
- What is the concrete definition of "borderline"? A margin band around the 4-BIP / 35%-concentration per-zone gate? A margin around the 10/25-BIP sample gates? Both?
- Where does it render -- a marker in the existing confidence column, a distinct cell treatment, or part of the Tier 2 LLM rationale sentence? (uxd + coach decision.)
- Is it computed deterministically by the Tier 1 engine (a `is_borderline` flag on the per-position row) or surfaced as a phrase by the Tier 2 LLM layer? Deterministic is more reproducible and matches E-228's Tier 1/Tier 2 split philosophy.
- Does it need a new `batter_positioning` column, or is it derivable at render time from `bip_count` + `zone_concentration` against the gate constants?

## Notes
Split out of E-228-07 during Codex spec review iteration 1 (finding CX-3). It was originally written into E-228-07 AC-1 as an optional "MAY surface a borderline-case flag" clause -- an optional feature inside an acceptance contract, which leaves scope and tests undefined and would expand E-228-07 against its own scope-discipline section. Moved here as a clean future-iteration capture. E-228-07's Context section references this idea by ID.

Related: the E-228 Rollout note (operator calibration pass) is the natural trigger point. The deterministic-vs-LLM question mirrors E-228's settled Tier 1/Tier 2 architecture (TN-1) -- a borderline flag is a threshold fact, which argues for Tier 1.

---
Created: 2026-05-15
Last reviewed: 2026-05-15
Review by: 2026-08-13 (90 days)
