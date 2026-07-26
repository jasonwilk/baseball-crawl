---
name: check-reachability-before-adjudicating-direction
description: Before adjudicating WHICH WAY a disputed claim goes, check whether it fires at all — a dispute hands you a framed question whose premises both parties already granted. Plus: give reasons not verdicts, and record which axes a sweep held CONSTANT.
metadata:
  type: feedback
---

**When you arrive at a claim through a disagreement, check reachability before direction.** A dispute hands you a pre-framed question, and a framed question is one whose premises have already been granted by both parties — so the cheapest decisive check is the one nobody performs.

**Why:** E-276 spec audit, 2026-07-25. Four participants (SE, DE, a second reviewer, me) argued across three rounds about the *direction* of an exempt-filter asymmetry — fail-open or fail-closed. One grep settled that it fires **nowhere**: the filter existed on one grain only, that grain had no gate for it to skew, and the cap it fed was provably invariant to it. The grep was available the entire time and cost nothing. We checked the computation and never asked whether the computation is reached.

That was the last of ~17 defects in one session, spread across every participant, with **not one arithmetic error among them**. Every single one was a correct local computation carrying a wrong claim about where it applied. The final one was a different species: a correct computation whose case never arose.

The one-sentence form, which covers both: **distrust the step from a correct result to a claim about where it applies — including the claim that it applies at all.** Note what this does NOT reduce to. It is not carelessness, and none of the standard disciplines reach it: *verify your claims*, *execute rather than derive*, and *attack the frame* all operate on one side of that step or the other, never on the step itself.

**How to apply:**

1. **Reachability first, direction second.** Given a disputed claim, grep for whether the mechanism is wired in before adjudicating its behaviour. "Does this fire?" is usually one command; "which way does it fire?" is usually a sweep.
2. **A moot finding is recorded conditionally, not deleted.** State the mechanism, mark it moot, and name the triggers that wake it. Deleting loses the reasoning; leaving it live overstates it.
3. **Give reasons, not verdicts** — and demand reasons from others. DE's formulation: *a verdict that happens to be right in most of its range is unfalsifiable in the part where it is wrong.* Three times in that session a stated reason was falsified while its conclusion survived, and each time **only because the reason was stated**. This is the practical case for the epic-spec convention of recording rulings with their reasoning attached.
4. **Record which axes a run held CONSTANT, not just what it covered.** Every participant generalised from a region while holding executed evidence about another — DE twice, once with the counterexample sitting in its own scratchpad in a different file for a different purpose. "Have I run this region?" is answerable from a run list; "did any run vary churn?" is not, unless the constants were recorded. Structural, not individual — four people, one session — so the corrective is indexing rather than diligence.
5. **Prefer a column that SHOWS the property over an inference that implies it.** I inferred "today is healthy in this band" from a permit; DE added a `churn_left_after_healthy` column that showed it directly, and that made the disposition unarguable. The executed-vs-derived distinction applies to your own evidence tables, not only to other people's claims.

Companion to [[inventory_frame_omits_the_primitives_own_tests]] (the same failure at inventory/sweep scope, including my own falsified rule) and `.claude/rules/tool-output-integrity.md` ("a verdict's stated REASON rots independently of the verdict").
