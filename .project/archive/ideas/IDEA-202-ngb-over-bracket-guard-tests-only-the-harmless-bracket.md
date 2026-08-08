# IDEA-202: The ngb-beats-bracket guard is tested only on the bracket where it cannot fail

## Status
`CANDIDATE` — **relayed, not re-verified. Read the test before acting.**

## Summary

`test_legion_ngb_beats_14u_bracket` (`tests/test_league_detection.py`) asserts that a recognized `ngb` outranks a mapped age bracket. Per the E-275 spec seed, it does so using **14U — the one bracket where the assertion cannot distinguish a working precedence rule from a broken one**, because 14U resolves `youth_travel` rather than to a competing league. 15U and 16U (which resolve `nrbl`) and 17U/18U (which resolve `legion`) are the brackets where ngb-over-bracket actually has something to beat, and per the seed they are untested in this role.

**Sourcing, stated plainly: this is the one of the four E-275 MINORs I did NOT re-verify against the source.** The other three were re-read; this one is carried on the seed's word, and that seed was found during E-275 planning to carry five claims that did not survive checking. The test name and its location are confirmed to exist; the characterization of its weakness is not. **Read the test body first.**

## Why It Matters

A guard test that passes for a reason unrelated to the property it names is worse than no test: it occupies the slot where a real guard would go, and it reports health. This is the "a check that RAN is not a check that WORKED" shape from `.claude/rules/tool-output-integrity.md`.

The precedence it guards is load-bearing — a recognized governing body outranking an inferred age bracket is one of the classifier's core rules, and its sibling guards (`test_usssa_ngb_beats_15u_bracket`, `test_usssa_ngb_beats_18u_bracket`) suggest the pattern was applied more carefully elsewhere, which is itself worth checking rather than assuming.

## Rough Timing

**Fold into the next epic touching the classifier's test suite.** Cheap — extending an existing parametrization, most likely. E-275's fixture pack does not close this: that pack is ground-truth over input shapes, while this is a targeted precedence guard, and the two answer different questions.

## Dependencies & Blockers
- [ ] None, beyond reading the test.

## Open Questions
- Does the seed's characterization hold? First step, before anything else.
- Are the sibling `usssa` guards stronger, or do they have the same shape? If the whole family is weak, this is a small sweep rather than a one-test fix.
- Is there a general form worth having — every recognized `ngb` against every bracket bin — or is that more matrix than the property needs?

## Notes

Out of scope for E-275 by operator ruling — one of four adjacent MINORs captured rather than built.

**Do not cite this idea as evidence the test is weak.** Cite it as the reason to look.

Related: [[IDEA-209]], [[IDEA-210]], [[IDEA-201]] (the other three MINORs), [[IDEA-178]] (the `ngb=american_legion` shadow, which is about the same precedence rule doing something unintended rather than being under-tested).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
