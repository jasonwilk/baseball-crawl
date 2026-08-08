# IDEA-216: Sweep-style ACs must FORBID "correcting" an accurate citation

## Status
`CANDIDATE`

## Summary
An acceptance criterion that tells an implementer to enumerate citations and *"correct
or verify accurate"* each one **permits** the right outcome without **forbidding** the
wrong one. The next sweep-style AC needs a **⛔ naming the non-member that must
survive** — an accurate citation must NOT be "corrected" — with **resolve-each-symbol-
to-its-`def`** as the named operation.

## Why It Matters

**`ca-2`'s sentence, which is the whole payload:**

> **An AC that permits the right outcome does not thereby forbid the wrong one.**

**The comparison that makes this actionable rather than an aphorism, and both halves
shipped in the SAME epic:**

- **E-277 story 04's AC-6a** said *"corrected **or** verified accurate"* — a
  **disposition**, with no ⛔ naming what must not change.
- **Story 05's AC-8, next door**, named **the file that must not be touched** — a
  byte-identical twin sentence that a literal instruction would have edited.

Same trap shape, one AC protected against it and one not.

**AC-6a still PASSES the reachable-red test.** *"Record each citation with its verdict"*
is checkable, and the Notes carry `ACCURATE — left alone`. **Falsifiable and preventive
are DIFFERENT PROPERTIES, and this AC has only the first** — which is the reusable
insight, because reachable-red has been the most productive AC instrument this project
has and this is its honest limit.

**The evidence is better than an experiment could have produced, and that bounds any
future review of this class.** A clean diff **cannot** distinguish *"the AC prevented
the wrong edit"* from *"the implementer happened to check"* — **the two are
byte-identical.** No amount of reviewing produces that discrimination. It was settled
only because `ca-2` reported the **mechanism** rather than the outcome, from the one
position that could: *it held because the implementer resolved each symbol to its
definition before editing, not because the AC blocked the edit.*

## Rough Timing

**Promote when the next sweep-style AC is written** — any AC of the form *"enumerate
every X and correct each"*. There is nothing to fix retroactively: E-277's delivered
sweep was correct, and this is a defect in an AC's **text**, for its next author.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- Does this belong in `.claude/agents/product-manager.md` (the AC-authoring audience) or
  in a rule file? **Likely the agent definition** — it binds only when someone is
  WRITING or AUDITING an AC, and putting it in an always-loaded rule taxes every agent
  on every turn for a rule with a narrow audience. That reasoning moved four related
  items during E-277's closure codification; this one arrived too late to ride it.
- Is the ⛔ + named-operation shape general enough to state once, or does each sweep AC
  need its own non-member named? **The named operation generalizes; the non-member does
  not** — someone has to know which citation is the accurate one, which is why the
  operation (resolve to `def`) is the transferable half.

## Notes

**⛔ THIS IS NOT A FINDING AGAINST E-277 STORY 04, and the filing is deliberate.** Story
04 **satisfied** AC-6a and its delivered sweep is correct — it reported the accurate
`_query_freshness` citation as ACCURATE and left it alone. **A story must not carry a
finding against itself for a weakness in a criterion it met**; the defect belongs to the
AC's text and its audience is the next author who copies the shape.

**The hardening was deliberately NOT landed in E-277.** The delivered work already
satisfied a stronger form, so tightening would have changed nothing about that story —
and tightening an AC after implementation and approval is the same move that was refused
for the `ReclaimResult` fold ([[IDEA-215]]). Filed rather than retrofitted, on that
reasoning.

**Credit: the sentence is `ca-2`'s.** `cr5` explicitly declined it, its own account being
that it *turned a verdict into a property of the instrument, which is cheap once someone
else has done the measurement.* The measurement was `ca-2`'s. Recorded because a false
credit outlives a false claim.

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
