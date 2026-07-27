# IDEA-206: `\bjuniors\b` may be aimed at the wrong word form — hypothesis, not a finding

## Status
`CANDIDATE` — **explicitly a hypothesis. baseball-coach requires a citation-grade check of real Legion naming convention before anyone touches the regex.**

## Summary

`\bjuniors\b` is one of four Legion-family patterns in `_LEVEL_WORD_PATTERNS`, matching the **plural noun**. baseball-coach's hypothesis is that Legion's own division naming uses "Junior"/"Senior" **adjectivally** ("Legion Junior division"), which a coach naming a team would render **singular** — "Post 9 Junior", not "Post 9 Juniors".

The corpus evidence is consistent with that and is the reason the hypothesis exists:

- `\bjuniors\b` (plural): **0 of 563 names, 0 of 2,518 raw bodies.** Entirely unattested.
- Singular "Junior": **4 occurrences, all four "Junior Varsity"** — a high-school pairing, not Legion. Zero "Junior Legion".

So the pattern as written may match a form nobody uses, while the form people do use appears only in a context where it means something else.

**`seniors` breaks the pattern** — 8 attestations, more than the hypothesis predicts. Coach's read is that "Seniors" carries an ordinary, very common non-Legion English meaning (graduating class) that plural "Juniors" does not carry as readily, which is also what makes it misfire (see [[IDEA-205]]).

## Why It Matters

If the hypothesis holds, `\bjuniors\b` is dead code — a pattern that has never matched anything and never will, occupying a precedence slot and appearing in guard tests as though it were live. That is a small cost, but a misleading one: it makes the Legion-family vocabulary look better covered than it is.

The sharper consequence is the inverse. If real Legion teams **do** name themselves with a singular "Junior", the classifier is missing them entirely — they fall through the Legion patterns to whatever else the name carries, or to `unknown`. That is a coverage gap rather than a misclassification, and nothing currently would surface it.

**Both readings are speculative.** The one thing established is the attestation count.

## Rough Timing

No urgency. Promote alongside any work on [[IDEA-205]] — same pattern family, same question about whether these two patterns earn their place — or when someone has a citation-grade source on American Legion team-naming convention.

## Dependencies & Blockers
- [ ] **A citation-grade check of actual Legion team-naming convention.** Coach was explicit: do not change the regex on recall. This is the same discipline applied to every numeric and regex claim in coach's rulings file, and it is the blocker.

## Open Questions
- Does American Legion baseball name its divisions "Junior"/"Senior" adjectivally, and how do member programs actually render that in a team name? The whole hypothesis turns on this.
- If singular "Junior" should match, **how do you avoid matching "Junior Varsity"?** That pairing is 4 of 4 observed singular occurrences and means the opposite — a sub-varsity high-school squad. A naive singular pattern would classify every JV team as Legion, which is a far worse defect than the one it fixes. Any fix must handle the collision first, and `junior varsity|jv` already sits ahead of the Legion patterns, so ordering may already do the work — **check before designing around it.**
- Is 563 names enough to conclude "unattested"? For a claim of absence, that depends on the base rate of Legion teams in the corpus — 22 names carry a Legion token. Absence within 22 is much weaker evidence than absence within 563, and this is exactly the denominator error that had to be corrected once already in this family (see [[IDEA-172]] notes).
- Should the pattern simply be **removed** rather than retargeted? If it matches nothing and its intended target is ambiguous with "Junior Varsity", removal may be the honest answer.

## Notes

Recorded at coach's request as **NOT an E-275 scope item** — flagged for the record during the RULING 4 narrowing, where `juniors` was held unpromoted alongside `seniors` as a judgment call rather than a corpus finding. Coach's words on that pairing: they are one lexical family, and `seniors`'s demonstrated ambiguity is *suggestive, not proof*, that its cousin carries the same risk.

Hypothesis of record: the **RULING 4 AMENDMENT** in `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`.

Related: [[IDEA-205]] (the observed `seniors` misfire — evaluate together), [[IDEA-172]] (the precedence question), [[IDEA-176]] (a singular/plural gap on a different pattern — `sophomore` — suggesting the vocabulary was not built with word-form variation in mind at all).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
