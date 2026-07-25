---
name: finding-withdrawal-shared-branch-reasoning
description: "Same code branch" is not a reason to withdraw a test-coverage finding — enumerated cases over distinct patterns add real discrimination.
metadata:
  type: feedback
---

Do not withdraw a request for additional test cases on the grounds that they "exercise the same branch." Check whether the cases route through **distinct predicates** on the way to that branch; if they do, enumeration adds discrimination, not redundancy.

**Why:** in E-272-02 I asked for `14U Reserve` and `14U Varsity` coverage, then withdrew the `14U Varsity` sibling after reasoning that the age-bracket ladder returns before any level word is consulted, so both names hit one shared return. That was true and incomplete. SE instead enumerated four names, and the four route through four different `_LEVEL_WORD_PATTERNS` entries — `jv`, `freshman`, `reserves?`, `varsity`. A single-name test stays green if someone later hoists one pattern above the ladder or special-cases `varsity`, which is exactly the edit the pin exists to catch. SE's broader test was better than what I had signed off on.

**How to apply:** when weighing "is this test case redundant?", ask what a plausible future edit would break. If the cases differ in which pattern, branch, or lookup they traverse *before* converging, they are not redundant. Say plainly that the implementer's version is better when it is — conceding improves the next round more than defending the earlier call does. This is the same discipline as [[ratio_gate_population_claims]] and [[stale_defect_characterization]]: a hand-derivation that holds for the case in front of me can be wrong about the general shape.
