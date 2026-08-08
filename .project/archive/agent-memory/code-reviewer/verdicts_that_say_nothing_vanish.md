---
name: verdicts-that-say-nothing-vanish
description: A "no change needed" ruling and a clean APPROVED both produce no artifact effect, so both disappear from the record; write every surfaced line's verdict down and attach a tree SHA to every verdict at the moment you issue it.
metadata:
  type: feedback
---

**Every surfaced line gets a WRITTEN verdict, "no change needed" included; and every verdict travels with its anchor — `APPROVED @ <tree-sha>`, `<figure> @ <tree>` — recorded at the moment it is issued, not reconstructed later.**

**Why:** the two halves are one problem. A sweep hit you rule harmless and a review you rule clean both **cause no change to any artifact**, so neither leaves a trace, so neither can be verified to have happened. `dispatch-pattern.md`'s receipt rule — *verify delivery by looking for the change your message should have caused* — is explicit that it reaches **actionable findings only**, and a clean verdict is precisely the excluded class. Its converse is unavailable too: absence of an artifact effect tells you nothing *unless* you can show the artifact was written after your send.

E-280 produced both halves in one dispatch:

- **The clean-verdict half, measured.** My E-280-06 review verdict was delivered and the epic's dispatch scorecard nonetheless read `| 06 | fb15272 | **UNRECORDED IN THE ARTIFACT** | **UNRECORDED IN THE ARTIFACT** |`. It was not a relay failure: `epic.md`'s mtime was `06:08:10Z` and my send was `06:08:36Z`, so the row was written 26 seconds *before* the verdict arrived and simply stayed that way. **A real verdict, really delivered, absent from the record** — and the only reason I could settle it rather than argue about it was that I had the two timestamps. Note that the mtime comparison is also what makes "no effect" *interpretable*: without it, an unchanged artifact is consistent with both a lost message and a message that arrived after the write.
- **The no-change-needed half.** My layer-wide semantic pass surfaced ~25 sites. Twenty-plus resolved to "current, no change" and one was the live carrier. **The verdict on the twenty is what makes the one credible** — an "all clear" floor is a SUCCESSFUL sweep, not a wasted one. Ruling silently on the harmless sites would have left me asserting a conclusion with no visible basis, and left the next reader unable to tell a swept site from an unswept one.

**⭐ A DELTA NEEDS TWO ANCHORS, AND THE ONE YOU OMIT IS ALWAYS THE BASE.** `<figure> @ <tree>` exists because a bare number is a position. **A bare COMPARISON is a position too, and it needs `<delta> @ <base> → <tree>`.** I got this exactly half right at E-280's closure: I labelled my reading `87,752 @ tree 1c425fa` — correct — and then wrote *"the entire +1,728 of drift is `tool-output-integrity.md` alone; no other always-on file moved"* with **no base named at all**. True against `a5b65eb` (verified: every other always-on file is `+0` there). **False against the merge base**, where three others had moved — `dispatch-pattern.md` +1,047, `worktree-isolation.md` +565, `workflow-discipline.md` +24. **The refuting data was in a table I had printed in the same message.** CA labelled it a missing-label rather than an error, correctly: my base was the right one for the question I was answering, and *"a correct observation against the WRONG BASELINE"* is a five-instance pattern here, so contradicting me from a different base would have been the sixth. **You hold your base implicitly, which is exactly why it is the half that goes unwritten** — the reader does not, and a comparison is the one figure that is *meaningless* rather than merely imprecise without it.

**How to apply:**
- In any sweep, audit, or enumeration, emit a verdict line per surfaced site. Do not collapse the clean ones into "the rest were fine" — that sentence is where an unresolved site hides, and it binds the implementer as much as the reviewer.
- Issue every verdict as `<verdict> @ <tree-sha>` (or `<figure> @ <tree>` for a measurement). A bare verdict is a position, not an object, and it gets applied after the tree has moved. This is CA's *name the OBJECT, not the POSITION* — see [[tool_gotchas]].
- Where an outcome legitimately has no artifact effect, say so and name what you *can* offer instead: a timestamp, a tree SHA, a quoted command and its output.
- Do not report "delivered" from a successful send. Report it from an observed effect, or report the send with its time and say the delivery is unverified.

Related: [[closure_diff_growth_after_integration_review]] (the anchor is what makes closure growth mechanical to compare), [[past_tense_prediction_in_a_batch]] (the other way a claim about your own action goes wrong).
