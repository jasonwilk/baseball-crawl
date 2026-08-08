---
name: finding-severity-needs-the-callee
description: A call site proves a value is CONSTRUCTED, never that it is CONSUMED — follow the argument into the callee before assigning severity to a "surface X renders Y" finding.
metadata:
  type: feedback
---

Before calling a site a user-facing surface, follow the value into the callee and confirm it is
actually consumed. A call site shows a value is BUILT and PASSED; it says nothing about whether
anything reads it.

**Why:** E-278 iteration 1, a finding of mine that I had to retract. I flagged
`src/reports/generator.py` building `team_record_str = f"{record['wins']}-{record['losses']}"` and
passing it as `team_record` into the Tier-2 LLM enrichment, and I rated it **coach-facing** — the
most serious surface in that finding — reasoning that Tier-2 narrative renders on the report page.
That reasoning is sound about the enrichment and wrong about the parameter.
`src/llm/../reports/llm_analysis.py` documents `team_record` as *"accepted for call-site
compatibility but intentionally unused: the validated Variant A block drops the records section"*,
and repeats it in the second function's docstring. The string is built and discarded. One Read of
the callee refuted a severity I had already shipped.

Note what made it plausible: everything I actually observed was true. The string IS two-part, it IS
passed toward the LLM, and the enrichment DOES render. The defect was entirely in the unexamined
step between "passed" and "consumed" — which is invisible from the call site and cheap from the
callee.

**How to apply:** Any finding whose severity rests on "this reaches the user" owes one Read of the
consuming function before it is written down. Watch for the tell in the callee: a parameter kept
for call-site compatibility, an `Accepted for ... compatibility` docstring line, or a `**kwargs`
that swallows it. When the value turns out to be dead, the correct disposition is usually a recorded
"no change needed — value unused, see <file:line>" verdict under whatever enumeration criterion
covers it, NOT a code change and NOT silence.

Two things that generalize past this instance. **A dead-but-constructed value can still be caught by
a criterion phrased as a universal** ("no code path produces X") — so the finding may survive at
lower severity even when the harm is nil; separate "is it caught" from "does it matter" and say
both. And **retract in the same channel and with the same prominence as the original claim**: I put
the retraction in the report body and in the relay to PM, marked "do not triage as a defect,"
because the team lead had already quoted my wrong severity back to me in an ack. Related:
[[ratio-gate-population-claims]], [[finding-withdrawal-shared-branch-reasoning]].
