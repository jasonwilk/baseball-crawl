---
name: regenerate-the-population-not-the-pair
description: CALIBRATION — my own twice-in-one-session failure: I compared the two statements/sites I already had instead of regenerating the full set, and both times someone else found the third.
metadata:
  type: feedback
---

When auditing an enumeration, **regenerate the population from the authority; do not diff the
members you happen to be holding.** Two of my own misses in one session (E-279 planning), same
root cause, both found by someone else:

1. **The third statement.** I filed "TN-8c lists four residuals, E-271's History lists six." I
   diffed those two and stopped. PM found a THIRD count in `epic.md` itself — the OQ-2
   sub-bullet says **five**, eleven lines from the four. Two contradictory counts of one set in
   one file, and I never looked for a third statement because I already had a discrepancy worth
   reporting. True set was eight.
2. **The unruled line.** My token sweep of PM's memory printed three hits; I reported two and
   never gave the third a verdict. It surfaced in my OWN grep output. PM found it independently.

**Why:** finding *a* discrepancy feels like completing the check — it produces a reportable
finding, so the search stops with the question answered rather than the population enumerated.
This is the reviewer-side twin of the exhaustive-class rule I apply to others, and I violated it
in the same report where I flagged incomplete enumerations in two stories.

**How to apply:** (a) when you find one inconsistency in a claimed set, that is the START of the
sweep — grep the whole artifact for every restatement of the same set before writing it up;
(b) **every line a sweep surfaces gets a written verdict, "no change needed" included** — the
worklist/scan distinction in `.claude/rules/tool-output-integrity.md` binds the reviewer as hard
as the implementer; (c) prefer a remedy that is immune to an incomplete list (require a verdict
per surfaced line) over one that patches the list (name the missing site) — PM's version of my
finding superseded mine on exactly this ground.

**And do not accept absolution that detaches the lesson.** PM generously noted it found the
unruled line on an independent sweep rather than by reading my output. True, and it does not
change what I failed to do with a line in my own results. Keep the lesson attached.

Companion to [[new_gate_inherits_hook_enumeration]] (execute the case, do not reason about it)
and the enumeration rules in [[enumerate_backwards_from_the_cited_artifact]].
