# IDEA-201: Two level-word matchers on the same words disagree — substring vs. word boundary

## Status
`CANDIDATE`

## Summary

`src/reports/starter_prediction.py` matches the same vocabulary of level words in two places, by two different methods. Confirmed by reading both, not relayed:

- **`_nsaa_level_from_name`** (the `ngb=nsaa`/`nfhs` disambiguation path) does `if keyword in name_lower` over `("jv", "junior varsity", "freshman", "frosh", "reserve", "sophomore")` — **bare substring**.
- **`_LEVEL_WORD_PATTERNS`** (the empty-`ngb` path) uses compiled regexes with `\b` word boundaries.

So the same name classifies differently depending on which path reaches it. A name containing `Sophomores` matches the substring test but not `\bsophomore\b`; a name containing an embedded `jv` sequence matches the substring test on any word containing those two letters.

## Why It Matters

The divergence is invisible from either call site — each function reads as correct on its own — and which one runs depends on whether the team declared an `ngb`, a property of the opponent's data rather than of anything we control. Two teams with identical names can resolve differently.

The substring side is the looser one and is where the surprises live: `in` has no notion of a word, so the matcher's behaviour on any name nobody has tried is genuinely unpredictable rather than merely undocumented.

This is the general case of [[IDEA-176]], which captures the specific `sophomore`/`Sophomores` plural gap. Fixing the general divergence would subsume it; fixing 176 alone would leave the two matchers still disagreeing on everything else.

## Rough Timing

**Fold into the next epic touching either matcher.** Not urgent standalone — no observed misclassification is attributed to it — but it is the kind of defect that makes *other* defects hard to reason about, because "which matcher ran?" becomes a question for every name-related finding.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- **Which behaviour is correct?** Not obvious, and it should be ruled rather than assumed. Word boundaries are more precise, but the substring matcher's tolerance may be catching real-world names with punctuation or concatenation that `\b` would miss. A ruling wants a look at real names first — a 563-name corpus now exists at `proxy/data/sessions/` (see [[IDEA-172]]'s notes for provenance).
- Should there be **one** matcher rather than two? The canonical-seams principle in `CLAUDE.md` says a second path to something that already has one is the recurring defect here, and this is a clean instance. But the two paths return different things (a league id vs. a level class), so unification is more than deleting one.
- Does the same doubled-vocabulary pattern appear elsewhere in the classifier?

## Notes

Out of scope for E-275 by operator ruling — one of four adjacent MINORs captured rather than built. E-275 reorders entries *within* `_LEVEL_WORD_PATTERNS` and does not touch `_nsaa_level_from_name`, so it neither fixes nor worsens this.

Surfaced by the audit-starter sweep via the E-275 spec seed; **both matchers re-read against the source during E-275 planning** rather than inherited.

Related: [[IDEA-176]] (the plural sub-case — subsumed by fixing this), [[IDEA-209]], [[IDEA-210]], [[IDEA-202]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
