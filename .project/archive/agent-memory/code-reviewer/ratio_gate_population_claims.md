---
name: ratio-gate-population-claims
description: When recommending a change to a ratio/threshold gate's counted population, never assert "this introduces no false refusals" from hand-derivation — it fails at small N.
metadata:
  type: feedback
---

When a review finding recommends changing WHICH population a ratio gate counts (numerator or
denominator), state the recommendation but do NOT assert it is side-effect-free. Hand-derive the
direction, then require the implementer to verify empirically against the suite.

**Why:** E-267-02 MF-2. I found the real bug — the FLOOR_RATIO numerator counted the full schedule
array while the denominator counted only loaded (completed) games, so a truncated payload passed
`8 >= 7.5` and would mass-delete 11 games. Correct finding. But I added "I checked this does not
introduce false refusals," reasoning that a status reversion "drops the numerator by one." That holds
at N=30 and FAILS at small N: with 3 prior games, one reversion is a third of the population, and the
strict completed-only numerator gave `1 >= 1.5` → refuse, turning a genuinely voided game into a
permanent non-retire. SE hit it as a red AC-6 test. The fix needed a compensating term
(`prior_ids & fresh_game_ids` — prior games the array still vouches for).

**How to apply:** ratio gates have TWO failure directions — fail-open (the bug you usually catch) and
fail-closed (the regression your fix causes). Enumerate both, and evaluate at the SMALLEST realistic
N, not the typical one. A HS roster/schedule is 12-30 items, so "one item" is routinely 3-8% — never
negligible. Frame such recommendations as "verify empirically before landing."

Useful algebra for these gates: with numerator `C ∪ (P ∩ A)`, denominator `|P|`, and `a` = absent
prior items, the gate reduces to `a <= 0.5·|P| + |C \ P|` — i.e. "delete at most half the prior
population, plus any numerator members that can never be in the denominator." That last term is the
mismatch to hunt for; the `0.5·|P|` part is just the chosen FLOOR_RATIO doing its job, NOT a defect.

Related: [[tool-gotchas]].
