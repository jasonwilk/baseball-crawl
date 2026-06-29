# E-245-05: Update `key-metrics.md` FPS% definition for the data-bearing denominator

## Epic
[E-245: High-Fidelity Play Ingestion](epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/rules/key-metrics.md` will describe FPS% with the data-bearing
(charted-PA) denominator that E-245-03 introduces, so the rule no longer contradicts the shipped
behavior. This is a context-layer wording reconciliation — no code changes.

## Context
E-245-03 restricts the FPS%/P-PA/P-BF denominators to charted plate appearances (`pitch_count > 0`).
`key-metrics.md` currently states FPS% is "FPS / BF with no query-time exclusions — ALL PAs (HBP,
Intentional Walk, and all other PA outcomes) in the denominator," and claims this "matches
GameChanger." That wording is now stale and must be reconciled (epic TN-5 / TN-10). The distinction
to preserve: this epic adds an UN-CHARTED-PA exclusion (an un-charted PA has no real first pitch),
NOT an OUTCOME exclusion — HBP/IBB and every other charted-PA outcome still count in the denominator.
The "matches GameChanger" claim HOLDS because GameChanger computes its own FPS% over pitch-charted
PAs (the reason team-133's true FPS% is ~64%, not a value diluted by un-charted PAs). `key-metrics.md`
is a context-layer file, so this work is owned by claude-architect. **claude-architect consulted and
APPROVED the approach** (the charted-PA gate is the correct context-layer call and makes the
"matches GameChanger" claim MORE accurate) and proposed the exact replacement wording — see Technical
Approach (implemented verbatim at dispatch).

## Acceptance Criteria
- [ ] **AC-1**: Given `.claude/rules/key-metrics.md`'s FPS% bullet, when it is revised, then it
      matches the exact CA-proposed text in Technical Approach — charted-PA (`pitch_count > 0`)
      denominator, the un-charted-PA-exclusion-not-outcome-exclusion distinction, and the
      P-PA/P-BF-gated / QAB%-not-gated contrast — consistent with epic TN-5.
- [ ] **AC-2**: Given the "matches GameChanger" statement, when the bullet is revised, then that
      claim is preserved and sharpened with the charted-PA rationale (GameChanger computes FPS% over
      charted PAs), not deleted.
- [ ] **AC-3**: Given the CA-confirmed single-file scope, when the edit is made, then ONLY the FPS%
      bullet in `.claude/rules/key-metrics.md` changes — the QAB entry is NOT edited (it makes no
      denominator claim), and `.claude/rules/data-model.md` and the api-scout-owned glossary are NOT
      touched.

## Technical Approach
Replace the current FPS% bullet in `.claude/rules/key-metrics.md` (the "FPS% (first pitch strike %)"
entry) with the following exact text — CA-proposed during consultation; claude-architect implements
it verbatim at dispatch:

> - **FPS% (first pitch strike %)**: Pitching stat computed from plays data as `FPS / BF` (first
>   pitch strikes divided by batters faced), where the denominator is restricted to **charted plate
>   appearances** (`pitch_count > 0`). This is an **un-charted-PA exclusion, not an outcome
>   exclusion**: an un-charted PA has no recorded first pitch, so including it would treat
>   absence-of-data as a non-strike (the data-bearing-coverage principle in
>   `.claude/rules/data-model.md`). There are **no outcome-based exclusions** — HBP, Intentional
>   Walk, and every other charted-PA outcome are included in the denominator. This **matches
>   GameChanger's calculation method**: GameChanger computes its own FPS% over pitch-charted PAs (the
>   reason a team's true FPS% can be ~64% rather than a value diluted by un-charted PAs). The
>   `is_first_pitch_strike` flag is meaningful only for charted PAs — on an un-charted PA there is no
>   real first pitch to record. The same charted-PA denominator gate applies to **P-PA / P-BF**;
>   **QAB% is deliberately NOT gated** — it keeps an all-PA denominator (see the QAB entry).
>   **Coaching priority**: FPS% is the first stat coaches look at when scouting a pitching staff —
>   always surface it prominently.

CA grep-confirmed (rules dir + glossary) that ONLY this FPS% bullet is stale: the QAB entry makes no
denominator claim (the "QAB not gated" contrast lives inside the revised FPS% bullet above),
`data-model.md` needs no edit, and the api-scout-owned glossary needs no edit. Single-file scope is
correct — do not expand.

## Dependencies
- **Blocked by**: E-245-03 (this story documents the denominator behavior E-245-03 implements;
  the wording must match the shipped semantics)
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/key-metrics.md` (FPS% definition wording)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is the codified resolution of the closure context-layer item recorded in epic TN-10 — landing
it as a dispatch story (rather than at closure) keeps the rule from going stale mid-epic. No test
changes (documentation/context-layer only).
