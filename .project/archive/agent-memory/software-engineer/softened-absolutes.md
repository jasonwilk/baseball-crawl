---
name: softened-absolutes
description: A softened absolute is not a correct claim — it reads as more careful and stays false. The fix is decomposing the conflated questions, not adding caveats. Plus: a detection query that names a CAUSE is a standing liability.
metadata:
  type: project
---

# A softened absolute reads as more careful and is still wrong

**The rule:** when a universally-quantified claim is refuted, adding a bound to it
usually produces a *second* wrong claim that is HARDER to catch, because naming a
caveat is what a measured claim looks like. The way out is almost never a better
qualifier — it is noticing that one sentence is answering **two different
questions** and separating them.

**Why (E-278-04, 2026-07-28).** One operator-facing docstring sentence took three
attempts:

1. *"Case 2 cannot produce that shape on any live path"* + query keyed on
   `start_time IS NOT NULL`. Refuted by two ingest-path counterexamples.
2. Query keyed on `timezone IS NOT NULL` + a resolvability check, **with the
   false-positive class named in the prose**. Still wrong — and this version
   *looked* like the careful one precisely because it stated a bound. It sat
   above a sentence claiming the predicate CONFIRMS the cause, which the bound
   contradicted.
3. Correct, and not a hedge: **two positive claims instead of one qualified
   one.** "Which rows are undated" is exactly answerable (`game_date =
   '1900-01-01'`, complete by construction). "Which of those a backfill can
   repair" is exactly answerable (`AND start_time IS NOT NULL`). "WHY each one
   is undated" is **not answerable from stored fields at all**, stated as a
   prohibition with both escape routes named.

Nothing about attempt 3 is more carefully worded than attempt 2. It asks
different questions. **Care was never the missing ingredient**, which is why
"look harder" would not have produced it — a reviewer's decomposition did.

**⚠️ The reviewer's own account, and it is the reason this file exists rather
than a note-to-self about care:** *"the SECOND was the dangerous one — it named
a bound, which made it read as the measured version while still being an
absolute with a caveat bolted on. My review would have been likelier to pass the
second than the first."* So the hedged wrong claim is not merely harder for its
author to notice — **it is harder for a REVIEW GATE to stop than the bald wrong
claim it replaced.** Do not treat "a reviewer will catch it" as the backstop for
a claim you have just qualified; qualifying is what disarms them. The backstop
that works is constructing the rows and running them.

## The transferable shapes

**A claim that enumerates a CAUSE class from stored state is a standing
liability.** Reviewer's phrasing, worth keeping verbatim: *"an exhaustive-class
claim is a standing liability, and the version that stops claiming a complete
class is the one that stops being falsifiable."* If the cause must be
machine-readable, **RECORD it at write time** — never infer it from the row
afterwards. Two columns that are populated by independent expressions cannot
reconstruct which branch wrote a third.

**Two predicates can be wrong in OPPOSITE directions, and "neither works" is a
stronger result than picking one.** `start_time IS NOT NULL` MISSES real
degraded rows; `timezone IS NOT NULL` ADMITS undegraded ones. Establishing that
no discriminator exists beat adopting either. See [[endpoint-parsing-notes]] for
the concrete field mechanics (`start_ts or end_ts` vs `start_ts` alone; the
`ON CONFLICT` COALESCE that lets a sentinel date sit over a retained instant).

**A plausible mechanism that explains an observed failure is not the mechanism.**
I explained a `KeyError` with a causal story that fit the symptom, while the
traceback naming the raising side was already in my context. The failing side
was the test stub, not the code I was theorising about. **Read the traceback you
already have before writing the explanation.**

**A verification whose SCOPE matches the change cannot detect a scope defect.**
I "proved" a lockfile correct by re-running `pip-compile` on `requirements.in` —
the same file the change touched, therefore blind to the gap, which was in
`requirements-dev.txt`. A re-run that could not have failed is not evidence.
Match the check's scope to the **gate's** scope, not to the edit's.

## How these got caught (the part that decides where to spend effort)

Not one of the four was caught by its author re-reading. Every one was caught by
a second party opening the primary, or by EXECUTING the claim. The corollary
that actually changes behavior: **when a claim is about what a query returns or
what a branch does, construct the rows and run it** — a reviewer here
pre-registered two adversarial rows *before* the fix landed, which is what made
the third attempt checkable rather than merely plausible.

Related: [[enumeration-vs-reachability]] is the same family from the other side —
there the enumeration was right and a reachability rating was wrong; here the
enumeration itself was the over-claim.
