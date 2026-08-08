# IDEA-210: The `classification` compare is case-sensitive and fails toward the LESS strict table

## Status
`CANDIDATE` — **note the failure direction; this one is not benign.**

## Summary

In `detect_league_level`'s Priority 1 branch (`src/reports/starter_prediction.py`), a tracked team with `program_type="hs"` is routed by:

```
if classification in ("jv", "freshman", "reserve"):
    return "nsaa_subvarsity"
return "nsaa_varsity"
```

Confirmed by reading the source, not relayed: the membership test is against **lowercase literals with no normalization** of the incoming value. A `teams.classification` of `"JV"`, `"Freshman"` or `"Reserve"` misses every literal and falls to the default.

## Why It Matters

**The default is the less conservative table.** `NSAA_SUBVARSITY` requires 1/2/3/4 rest days at the 30/50/70/90 breakpoints; `nsaa_varsity` requires 0/1/2/3 at the same breakpoints and permits a higher declared cap. So a casing variant in one DB column moves a sub-varsity team onto a table that asks for **one less rest day at every tier** — the under-rest direction, which is the one this project treats as unacceptable.

This is the same class of defect as the name-precedence bug E-275 exists to fix, on a different signal and with a shorter path: no season ambiguity is needed to unmask it, only a capitalized string.

Severity is bounded by who reaches this branch — Priority 1 is DB-sourced and applies to tracked teams, so the population is our own program rather than arbitrary scouted opponents. That makes it *more* worth fixing on one reading (these are the arms we are directly responsible for) and less on another (the values are ours to control, so they are probably consistent today). **Neither reading has been checked against the live column** — nobody has looked at what values `teams.classification` actually holds.

## Rough Timing

**Promote on either trigger**: anything touching `detect_league_level`'s Priority 1 branch, or a single observed non-lowercase `classification` value in the database. The second is a one-query check and should probably just be run.

## Dependencies & Blockers
- [ ] None. The fix is normalization at the compare; the check is a `SELECT DISTINCT`.

## Open Questions
- What does `teams.classification` actually contain today? Unmeasured. If it is uniformly lowercase this is latent; if not, it is live.
- Is the value constrained anywhere on write — a canonical upsert, a CHECK constraint, an enum — or is it free text? That decides whether normalizing the read is sufficient or whether the write path is the real fix.
- The same question for `program_type`, compared against `"hs"`/`"legion"`/`"usssa"` in the same block with the same literal style.

## Notes

Out of scope for E-275 by operator ruling — one of four adjacent MINORs captured rather than built.

Surfaced by the audit-starter sweep via the E-275 spec seed; **mechanism re-verified against the source during E-275 planning** rather than inherited.

**Do not fold this into a fix for [[IDEA-209]] without thinking about it.** Both are case-normalization defects in the same function, which makes them look like one change — but they sit on different priority tiers, different data sources (DB column vs. API field), and fail in **opposite directions**: 199 fails toward less information, this one fails toward a looser table.

Related: [[IDEA-209]], [[IDEA-201]], [[IDEA-202]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
