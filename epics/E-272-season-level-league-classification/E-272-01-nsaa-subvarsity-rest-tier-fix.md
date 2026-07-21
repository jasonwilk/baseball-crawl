# E-272-01: Correct NSAA_SUBVARSITY rest tiers (0/1/2/3 → 1/2/3/4)

## Epic
[E-272: Season × Level → League Classification (+ NRBL)](epic.md)

## Status
`TODO`

## Description
After this story is complete, the `NSAA_SUBVARSITY` rest-tier constant in the starter-prediction engine encodes the authoritative NSAA Sub-Varsity curve (stricter than Varsity by exactly one rest day at every tier) instead of the current curve that is byte-identical to NSAA Varsity pre-April. This corrects a live under-resting bug: sub-varsity opponent arms are currently marked available a day too early at every pitch tier.

## Context
This is a pre-existing engine correctness bug, independent of the season/NRBL feature work, that the operator moved into E-272 (it formerly lived in E-263-02c AC-7). It runs FIRST because it shares files with E-272-02 and is a clean, standalone correction. See Technical Notes TN-5 for the authoritative curve, the source, and the named stale test. The baseball-coach model doc (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`, §"NSAA Sub-Varsity") is the authoritative rule source — the engine must be brought into line with it.

## Acceptance Criteria
- [ ] **AC-1**: The `NSAA_SUBVARSITY` rest tiers in `src/reports/starter_prediction.py` are corrected to the authoritative curve — one more rest day than NSAA Varsity pre-April at every tier (1/2/3/4 at the 1-30 / 31-50 / 51-70 / 71-90 breakpoints) per Technical Notes TN-5. The 90-pitch daily max is unchanged.
- [ ] **AC-2**: Given a sub-varsity arm and a varsity arm with the same pitch load, when eligibility is evaluated, then the sub-varsity arm requires exactly one more rest day at each tier (e.g. an arm that threw 31-50 pitches needs 2 rest days under Sub-Varsity vs 1 under Varsity). A test asserts this per-tier relationship.
- [ ] **AC-3**: The named stale test `tests/test_league_detection.py::TestSubvarsityRules::test_subvarsity_same_rest_tiers_as_pre_april` (which asserts `NSAA_SUBVARSITY.rest_tiers == NSAA_PRE_APRIL.rest_tiers`) is reconciled to the corrected curve per Technical Notes TN-5 — it now asserts the sub-varsity curve is stricter-by-one-day, not equal. Any other existing test that encodes the old 0/1/2/3 sub-varsity curve is discovered (per `.claude/rules/testing.md` test-scope discovery) and brought to the corrected curve in the same change.
- [ ] **AC-4**: No other rule-table constant is altered (`NSAA_PRE_APRIL`, `NSAA_POST_APRIL`, `LEGION`, `PITCH_SMART_15_18` unchanged), and no engine default is changed. The full suite is green.
- [ ] **AC-5 (primary-source provenance)**: The corrected `NSAA_SUBVARSITY` carries a brief source-provenance comment citing the NSAA 2022 Pitch Count Regulations (per Technical Notes TN-10); the corrected 1/2/3/4 tiers match that source's Sub-Varsity table exactly — max 90, flat year-round with NO April split (operator-verified 2026-07-21). This strengthens the "these calls are exact" basis from a primary source, not only the coach model doc.

## Technical Approach
Correct the `NSAA_SUBVARSITY` `PitchCountRules` rest tiers in `src/reports/starter_prediction.py` to match the authoritative NSAA Sub-Varsity curve in the baseball-coach model doc. Reconcile the stale equality test named in TN-5 and run the `starter_prediction` importer set (TN-7) to catch any other encoder of the old curve. Verify the corrected value against the coach doc before implementing; if the coach doc and the 1/2/3/4 value in `.claude/rules/pitch-rules.md` / the epic ever disagree, escalate rather than guess.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-272-02 (shares `src/reports/starter_prediction.py` and `tests/test_league_detection.py`; runs first for a clean staging boundary)

## Files to Create or Modify
- `src/reports/starter_prediction.py` (modify — `NSAA_SUBVARSITY` rest tiers only)
- `tests/test_league_detection.py` (modify — reconcile `test_subvarsity_same_rest_tiers_as_pre_april`; add the per-tier stricter-by-one-day assertion)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-272-02**: the corrected `NSAA_SUBVARSITY` constant that the season × level mapping selects for spring sub-varsity teams — so E-272-02's "these calls are correct" behavior selects into a right table.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Correctness win: exact rest eligibility for existing sub-varsity opponents (JV / Reserve / Freshman) on the shipped Most Likely Arms card — a behavior change to existing reports, which is why it is split from the additive NRBL/season feature into its own story/commit.
