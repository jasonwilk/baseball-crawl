# IDEA-183: The opponent resolution ladder's rung (c) accepts a single search hit without checking its season year

## Status
`CANDIDATE` — real, measured at **2 teams in 752**, low severity. Keep open as correctness cleanup; do **not** read it as a coach-facing risk.

## Summary

`_resolve_via_search` (`src/gamechanger/opponent_ladder.py`, rung (c)) resolves an opponent name to a `public_id` on an unambiguous single search hit — and **never looks at what season that hit belongs to.** Read in source, not relayed: it calls `search_teams_by_name`, returns `None` when `len(hits) != 1` (correctly conservative about ambiguity), and on exactly one hit reads `result["public_id"]` and returns it. Nothing in the function inspects `season`, and `src/gamechanger/search.py` contains no occurrence of `season` or `year` either.

So a name whose only indexed GameChanger presence is an **old** season resolves to that old profile, silently and with full confidence.

**This is a gap in an existing intent, not a missing intent** — which is why it is worth recording rather than shrugging at. The function's own docstring states the contract it believes it is keeping:

> *"zero hits … or 2+ hits (ambiguous) return `None` so the caller falls to rung (d) -- NEVER a hard failure, and NEVER a wrong-team auto-ingest."*

A stale-season hit **is** a wrong-team auto-ingest. The single-hit condition was designed to be the guard against exactly that outcome and does not catch this shape of it.

## Why It Matters

**Measured 2026-07-25 over all 752 distinct team names in the operator's database: 2 teams reproduce, both resolving exactly one season back (→2025).** That is the finding. The rest of this section is why the first-pass figure was five times larger, because the gap between the two is more instructive than either number.

An initial probe found 14 names resolving to a profile from a different season year, but it used a **more permissive matcher than production**. Re-checking each of the 14 against rung (c)'s actual single-hit condition:

| outcome | count |
|---|---|
| reproduces through rung (c) | **3** |
| refused by the existing `len(hits) != 1` guard | 11 |
| indeterminate | 0 |

and one of those 3 resolves **forward** (DB says 2025, search found 2026), making the DB row the stale side — a different problem that must not be counted here. **Net: 2.**

**The existing guard is doing most of the work, and the mechanism behind that is now CONFIRMED rather than hypothesised.** `post-search.md` records that `result.name` "typically includes year", so a currently-active team is indexed once per season under year-bearing names and returns 2+ hits — which rung (c) already refuses. Only a team whose **sole** indexed presence is an old season slips through as a single hit. Two consequences worth keeping:

- It explains why the population is small **without any credit to a year check we have not written**.
- The bound is therefore **GameChanger's naming convention, not our code.** If GC ever stops embedding the year in team names, active teams collapse to single hits and this population grows. That is the durable reason to fix it rather than close it.

**Severity, stated to match the measurement.** The realistic harm is scouting **last season's roster for one opponent**. The path is still unattended — `resolve_opponent` is called from `src/reports/morning_run.py:463`, the cron-invoked scheduled-report driver, with no operator at the keyboard — so the failure is silent and confident rather than loud. But "silent and confident" at n=2 with one year of drift is a **data-quality cleanup**, not a risk to a coach's decisions.

**The fix needs no extra HTTP call**, which is what keeps it worth doing at this severity: `hits[].result.season.year` is **already on every hit** — documented in `docs/api/endpoints/post-search.md` and re-verified there 2026-07-25 as part of the `result` key set that file calls COMPLETE and closed. The year is sitting in the payload rung (c) already holds and discards. (That same doc shows a response carrying both 2026 and 2025 hits, so cross-season results are normal output.) The change is a comparison on a field already in hand.

## Rough Timing

Low priority; correctness cleanup. **Not a reason to schedule work on its own.** Natural triggers:
- Someone next touching the ladder or `morning-run`'s resolution path — the marginal cost there is near zero.
- Any sign GameChanger has changed its team-naming convention, which is the one thing that would grow this population.

## Dependencies & Blockers
- [x] ~~Measure the reproducing subset.~~ **Done 2026-07-25 — 2 of 752.** No remaining blockers.

## Open Questions

- **Does downstream reference-date filtering render a stale-profile report empty rather than wrong?** Still **not traced — do not assume either way.** Much less load-bearing at n=2 than it looked at n=14, but keep it recorded: it separates "a wasted run and a confusing blank" from "a populated report built on last season's roster with no caveat," and only the second is a correctness problem.
- **Refuse, or prefer?** A year gate could return `None` (fall to rung (d), consistent with the existing conservative posture) or select the newest hit when several exist. Refusing matches the docstring's stated contract; preferring is more useful. A decision, not a detail.
- **Does `POST /search` accept a year/season constraint in the request?** Unchecked. If it does, constraining the query is a different and possibly cleaner fix shape than filtering the response.
- **What is the right reference year?** The DB record's season, the operating-season year, or the game date being resolved for — these diverge at season boundaries, which is exactly when a scheduled run is most likely to hit it.

## Notes

**Implementation trap to carry forward, from `post-search.md`:** `/search`'s `season` is an **object** `{name, year}`, whereas the public team profile's `team_season` is flat (`season` a bare string, `year` a sibling integer). That doc says explicitly: *do not carry a parser between the two.* Anyone adding a year gate here will have just been working in the flat shape (E-272 / E-274 territory) and is primed to make exactly this mistake. Along with the no-extra-call finding, this is the most reusable content in the file.

**One case deliberately excluded from the count.** Of the three single-hit resolutions, one resolved **forward** — the DB row carried the older season and the search found the newer one. That is the DB being stale, not resolution picking a stale profile, and folding it in would inflate this defect with a case that argues the opposite direction. Recorded so it is not rediscovered and re-counted; not scoped here.

**A distinction worth preserving, because conflating the two would repeat this session's dominant failure.** The wrong-season rows in the session's own 752-team classification table came from the **probe's permissive matcher**, not from rung (c). Same *class* — name → profile resolution with no year check — but a different code path, and attributing them to this defect would be the same population-vs-number error logged five times during E-274 planning. This idea covers rung (c) only.

Related: [[IDEA-181]] (TBD/tournament schedule placeholders becoming `teams` rows) — the same family, where **resolution accepts something it should refuse**; both are silent and both are invisible to a green suite. Also adjacent to [[IDEA-151]] (morning-run `opponent_links` resolve-once permanence), since a stale resolution that self-commits is harder to undo than one merely computed.

Found during the 2026-07-25 session by probing every distinct team name in the DB against live GameChanger, then sized by re-checking each hit against rung (c)'s actual condition. Consistent with the standing lesson from [[IDEA-178]] and [[IDEA-179]] — **this class is only ever found by running real inputs against ground truth** — and the sizing pass is the other half of that lesson, since the first pass overstated the defect fivefold and its most alarming examples were the ones that did not reproduce.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
