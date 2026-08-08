# IDEA-227: Two E-278 lessons exist only in dispatch completion reports

## Status
`CANDIDATE` — **⚠️ CHECK COVERAGE FIRST. Both may be partly codified already; this is a
coverage question before it is a codification task.**

## Summary

Two of E-278's strongest recurring lessons were stated in dispatch completion reports and
**never written to a durable artifact**. Neither is in
`.claude/agent-memory/software-engineer/`, because no memory window was open when they were
articulated and the implementer declined to move the diff unasked at the commit boundary —
the right call, and the reason this is an idea rather than an edit.

**1. software-engineer's, on why a supporting claim escapes checking:**

> *"A claim that supports a conclusion you believe is the least-checked sentence you will
> write, and a CENSUS is the shape most likely to be one."*

Its remedy, which is the sharper half: **name what is checkable; do not count what nobody
will re-count.** E-278's worked instance is `.claude/rules/data-model.md`'s *"All queries
across `src/` filter on `'completed'`"* — a census, wrong, load-bearing, and unchallenged
until an agent refused a relayed instruction and went and counted. PM reproduced the same
census claim in a story's Technical Approach under the words *"Verified against the current
file."*

**2. code-reviewer's, on remediation:**

> *"The fix is new code and enters the same blast radius as the code it fixes."*

**Two independent instances in this one epic**: story 01's replacement assertion was itself
inadequate, and story 05's blanket rename **broke the author's own forwarding sentence
written minutes earlier** — a fix generating a fresh instance of the defect it was fixing.

## ⚠️ Check coverage before codifying — both may be partly covered

- **Lesson 1 may be the AUTHOR-side statement of a class already added.** claude-architect
  codified **Class A's mirror** (a true clause welded to a false inference) into
  `.claude/rules/tool-output-integrity.md` at E-278 closure. That is the same family stated
  from the *reader's* side. Whether the author-side framing adds anything is CA's call —
  but **the census-shape remedy appears to be sharper than anything currently written**, and
  it is the actionable part.
- **Lesson 2 may already live in the code-reviewer agent definition.** CR referred to it as
  *"my own remediation-regression rule,"* which suggests it exists. **If it does, the two
  independent instances are still worth attaching as worked evidence** — the E-278 promotion
  gate for a behavioral lesson is that it cite a defect it demonstrably caught, and these
  two are exactly that.

## Why It Matters

A lesson stated in a completion report has the lifespan of the dispatch. The agents that
articulated these have shut down; the reports are not loaded as context by anything. E-278
itself produced three separate findings of this exact shape ([[IDEA-224]], [[IDEA-225]],
[[IDEA-226]]) — claims stranded in artifacts nobody re-reads — so leaving two more stranded
would be the epic's own lesson going unlearned at its closing boundary.

Lesson 1 in particular is the **author-side** counterpart to a rule this repo already leans
on heavily, and the census shape is a concrete, recognizable trigger rather than a
disposition — it tells an author *which sentence* to distrust, which is rarer and more useful
than telling them to be careful.

## Rough Timing

**Promote when claude-architect is next spawned for any reason.** Deliberately NOT worth a
re-spawn: CA had shut down and the merge sequence was next when this was raised, and
re-opening codification at the commit boundary is the late scope growth that goes wrong.
Same disposition as [[IDEA-224]]/[[IDEA-225]]/[[IDEA-226]].

## Dependencies & Blockers
- [ ] **Requires claude-architect** — both targets are `.claude/rules/**` or an agent
      definition, and PM cannot write either.

## Open Questions

- **Does lesson 1 merge with Class A's mirror or sit beside it?** CA's call. The test is
  whether the census-shape trigger survives the merge; if it gets absorbed into a general
  statement about inferences, the actionable part is lost.
- **Is lesson 2 already written?** If yes, this reduces to attaching two worked instances.
  If no, note that CR believed it existed — which would make it a rule that lived only in
  its author's practice, an instance of the very gap this idea is about.

## Notes

Raised by software-engineer in its closing message at E-278 closure, unprompted, as a
decision rather than an omission. Filed 2026-07-28.

**Two attribution corrections from the same message, recorded in the epic's TN-18 rather
than here**, both made against their author's own interest: that SE's mutation probes and
input matrices *verified fixes* while **CR's question — "what wrong implementation still
passes this?" — found that two of those fixes were not fixes** (*"a probe confirms what you
thought to check; the question finds what you did not"*), and SE's observation that its
unprompted near-miss disclosures were **a response to the team making them cheap** rather
than a habit it brought.

Related: [[IDEA-214]] (the same problem one epic earlier — E-275's instrument-failure
catalogue stranded in a research file), [[IDEA-224]], [[IDEA-225]], [[IDEA-226]].

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
