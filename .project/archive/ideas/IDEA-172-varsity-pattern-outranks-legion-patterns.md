# IDEA-172: `\bvarsity\b` outranks the Legion patterns, and the season signal is masking it

## Status
`CANDIDATE`

## Summary
In `_LEVEL_WORD_PATTERNS` (`src/reports/starter_prediction.py`), the `\bvarsity\b` entry sits ahead of all four Legion-explicit patterns (`american legion|legion`, `post \d+`, `seniors`, `juniors`). First match wins, so `"Norfolk Legion Varsity"` with no season signal resolves `nsaa_varsity` — **an explicit "Legion" in the team name loses to "Varsity."**

## Why It Matters
The ordering itself is pre-existing (the pre-E-272 keyword table had the same relative order), and E-272 did not introduce it. What makes it worth capturing NOW is what E-272 changed around it:

**With `season="summer"`, the Varsity branch maps to `legion` anyway — so the resolution is correct, by a different route, and the ordering weakness is invisible.** The season signal is currently masking a name-ordering bug.

That masking is the whole reason to write this down. The weakness will look fine in every test and every live run right up until a summer Legion team arrives *without* a usable season signal — at which point an explicitly Legion-named team silently takes the NSAA Varsity table (110 max, 0/1/2/3) instead of Legion's (105, 0/1/2/3/4). A masked defect is more dangerous than a visible one precisely because the evidence of health is real: it genuinely does resolve correctly today.

Note this compounds with [[IDEA-168]]: that idea's two triggers are exactly the conditions that remove the mask. Season drift or season absence on a Legion-named Varsity team unmasks this ordering, so the two findings intersect rather than merely coexisting — the same missing signal that causes IDEA-168's Varsity divergence also exposes this.

## Rough Timing
No urgency on its own; promote alongside [[IDEA-168]] if that is picked up, since they share a trigger condition and a fix would naturally be reviewed together. Also a natural fold-in for anyone touching `_LEVEL_WORD_PATTERNS` for [[IDEA-171]]'s separator normalization — three of these ideas now point at the same function.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- **Is a pure reorder safe?** Moving the Legion patterns ahead of `\bvarsity\b` would make `"Legion Varsity"` resolve `legion` season-independently, which is probably right — a name carrying an explicit governing body should beat a generic tier word. But it needs the same care E-272's bracket ladder needed: check it against the existing guards (`test_seniors_14u_is_youth_travel`, `test_14u_juniors_is_youth_travel`) rather than assuming, since those already prove the BRACKET beats both families.
- Does the same "explicit body loses to generic tier" inversion exist elsewhere in the list? `"Post 12 Varsity"` would have the identical problem via `post \d+`.
- Is "Legion Varsity" a real naming convention, or a constructed example? Worth one check against live team names before doing anything — if no such team exists, this stays parked indefinitely. api-scout's 18-team sample would be the cheap place to look.
- Should an explicit-body-plus-tier-word name log the ambiguity rather than silently picking one? Same observability theme as [[IDEA-168]] and [[IDEA-171]].

## Notes
Found by SE during E-272 Phase 4 follow-up questioning. **Pre-existing, not an E-272 regression** — E-272 changed the mapping the patterns feed, not their order.

Kept as an idea rather than folded into E-272: it is a new detection signal, not an epic AC, and the epic had already grown past its planned scope. SE offered to take it as a story within E-272; PM and team-lead both preferred the ledger, since it is not a regression and the epic's own Behavioral Changes list is already long.

Related: [[IDEA-168]] (shares the trigger that removes the mask), [[IDEA-171]] (same function, same "level-word matching is weaker than it looks" theme).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
