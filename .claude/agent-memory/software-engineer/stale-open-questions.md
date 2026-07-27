---
name: stale-open-questions
description: An artifact's recorded OPEN QUESTION is not evidence the question is still open — check for a later ruling before routing it as open work; hit twice in one session (E-275 planning)
metadata:
  type: feedback
---

**An open question recorded in an artifact is a claim about the moment it was written, not
about now. Before routing one as open work, check whether it has since been ruled.**

**Why:** in E-275 planning I did this twice in one hour, in a session where I was auditing
other people's claims for exactly this failure mode.

1. I told PM the defect's real-world reachability was "UNMEASURED... per IDEA-172's notes it
   was never run." IDEA-172's note predated api-scout's measurement. It had been run —
   `Legion Varsity` is 0 of 563 real names and the reorder is a 0-of-563 behavioural no-op.
   Compounding error: the instrument the note named (the "18-team sample") was an
   `age_group`-population probe that *"cannot answer a naming question and never could"*.
2. I routed api-scout's closing Legion+Reserve question ("nobody has been asked") as open.
   Coach had ruled it — epic TN-2, *"actively harmful in every non-summer branch, not merely
   unnecessary"*. My own measurement supported the premise, so I was reopening a question my
   own data had helped close.

Both times the artifact was accurate when written. Neither was stale in the ordinary sense
of being wrong — the *state of the world* moved past it.

**How to apply:** whenever an artifact hands you an open question, an "unmeasured", a "never
run", or a "nobody has been asked", treat it as **dated**. Before relaying it: check the
epic's Technical Notes and the relevant agent-memory files for a later ruling, and check
whether the instrument the note names is even the right one. This bites hardest in
relay-heavy planning, where the same question is discussed by several agents across hours
and only some of them write down the resolution.

Two second-order notes worth keeping:

- **Offered a narrower reading that would make me half-right, decline it.** Team-lead
  offered that my "unmeasured" claim might have been reaching at coach's bare-token
  falsifier (which genuinely *cannot* be run — 14 names against a 30-50 floor). It was not
  what I meant. Retrofitting would have been the *"verdict survived while its stated REASON
  was wrong"* shape that api-scout's own file names. Plainly wrong once beats half-right by
  reconstruction.
- **The same rot hits FIGURES, not just questions.** My blast-radius number (60 changes /
  5 names) was measured under a four-pattern move; coach later narrowed the ruling to two
  patterns and the real figure is 36 / 3. The number stayed true of what it measured and
  quietly became wrong for the question it was attached to. **When a ruling narrows, re-run
  every figure produced under the old premises** — nobody will ask you to.

Related: [[name-matching-gotchas]], [[testing-gotchas]]
