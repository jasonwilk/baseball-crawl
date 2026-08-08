# IDEA-085: Richer LLM data-block field-translations to match the validated Variant A SOT exactly

## Status
`CANDIDATE`

## Summary
Bring the Tier-2 LLM data block (`_format_pitcher_table` / `_pitch_display` in `src/reports/llm_analysis.py`) into exact alignment with two field-translations specified in the validated Variant A source-of-truth (`epics/.../E-243-04-narration-prompt.md`, "Field translations"), which the E-243-04 implementation consciously approximated rather than reproduced verbatim:

1. **Null-pitch IP-proxy `pitch_display`** — SOT specifies `"estimated {N}+ pitches"` where `N ≈ round(innings × 15)`. The shipped code renders the non-numeric `"an estimated recent workload (pitch count not on file)"` because the enriched candidate dict carries no innings field to derive `N`.
2. **UNAVAILABLE TODAY rows** — SOT specifies the structured form `"threw N pitches X days ago — needs M more day(s) of rest before eligible"`. The shipped code emits the engine's raw `reason` string (e.g. `"95p Jun 24, needs 4 days rest"`) because `unavailable_arms` carries only `{name, reason}`.

## Why It Matters
Both shipped forms are AC-compliant (no decimal-IP field per E-243-04 AC-8; jargon-free), functionally equivalent, and the LLM rewords them into prose anyway — so the gap is one of data-block fidelity to the validated SOT, not coach-facing correctness. Closing it would make the data block reproduce the bake-off-validated prompt exactly (removing the two documented deviations) and give the model slightly richer, more structured inputs for the null-pitch and unavailable cases.

## Rough Timing
Someday / nice-to-have — no urgency. The conscious-accept rationale at E-243-04 closure was "Simple first": reproducing the numeric/structured SOT forms requires threading additional fields (innings for the IP-proxy estimate; structured pitch-count/days-ago/rest-short for unavailable arms) through the E-243-01/-03 engine output, a scope expansion not justified by the cosmetic payoff.

## Dependencies & Blockers
- [ ] E-243 (probable-starter usefulness) shipped — establishes the Variant A prompt, `_pitch_display`, and the `unavailable_arms` `{name, reason}` shape this refines.
- [ ] Engine-output enrichment: candidate dicts would need an innings field (#1); `unavailable_arms` would need structured fields beyond `{name, reason}` (#2).

## Open Questions
- Is the numeric `"estimated {N}+ pitches"` form actually more useful to the model than the plain phrase, given the LLM rewords either into prose? (Validate before promoting.)
- For #2, is the structured unavailable form worth a richer `unavailable_arms` schema, or is the raw reason string (already shown identically on the deterministic card) sufficient indefinitely?

## Notes
Captured from E-243-04 code review: two SHOULD FIX findings DISMISSED as conscious-accepts by the team lead (2026-06-28). Finding #2 (pitch_display) and finding #3 (unavailable rows) are recorded here as a combined future-refinement idea. Parent epic: E-243. Related: E-243-04 AC-2 (Variant A SOT reproduction), AC-8 (no-decimal-IP guard), [[IDEA-083]] (per-arm estimate marker, the other E-243 deferral), [[IDEA-079]] (predicted-starter narrative richness).

---
Created: 2026-06-28
Last reviewed: 2026-06-28
Review by: 2026-09-26
