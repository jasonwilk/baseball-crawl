# IDEA-189: A Failing Player-Dedup Collapse Is Invisible to `LoadResult.errors`

## Status
`CANDIDATE`

## Summary

`dedup_team_players`' except block logs an ERROR with a traceback and continues — but does **not** increment `result.errors`. So a persistently failing collapse is visible in logs and **invisible through `LoadResult.errors == 0`**, which is the channel this codebase treats as authoritative for "did the mechanism complete cleanly."

That is a **swallow-without-count**, and it diverges from the swallow-**and**-count pattern documented as deliberate elsewhere in the same loader, where `game_loader.py` catches broadly, logs ERROR, and returns 1 into `result.errors` precisely so a failure is not lost. `.claude/rules/testing.md` builds on that pattern: *the result object is the evidence, a spy is not.* Here the result object is not evidence.

**And it is a CLASS, not a dedup quirk.** Verified across all five swallow sites in the scouting load:

```
scouting_loader.py  _load_team_core, dedup sweep         except -> logger.error   NO count
scouting_loader.py  _reconcile_absent_games              except -> logger.error   NO count
scouting_loader.py  the exempt pre-plan (_pending_...)   except -> logger.error   NO count, returns None
scouting_loader.py  ...and its caller                    WARNING "Roster retire SKIPPED"
scouting_loader.py  the roster reconcile                 except -> logger.error   NO count
game_loader.py      the player-line reconcile            result.errors += ...     <- the ONLY counter
```

⚠️ **Cited by FUNCTION, not line — the original line numbers (`:318 :432 :521 :593 :622 :679`) had all ROTTED by 2026-07-26**, moved by E-276 stories 01 and 02 editing the same files. **Re-verified in source at that date**: the shape holds at every site above, unchanged. The rot is why the anchors changed; the finding did not.

**So a run in which the game reconcile, the roster reconcile, the exempt pre-plan AND the dedup sweep all failed still reports `LoadResult.errors == 0`.** Four of five maintenance-path failures are invisible to the result object.

**Note the inversion, because it changes how the gap should be described**: swallow-with-count is **not** a norm the other sites depart from. **It is the single exception**, and it happens to be the one grain `.claude/rules/testing.md` documents. Write it as *"only player-line counts,"* never as *"dedup deviates"* — the second implies four sites drifted from a standard, when the standard was never general.

## Why It Matters

An operator or a test checking the result object sees a **clean load** while a collapse fails on every run.

The concrete consequence is a **split identity that does not self-heal**: a component the planner keeps trying to merge and never merges leaves two `player_id`s for one human, each carrying part of a season. Nothing in the authoritative channel says so.

**⛔ AND THE CONSEQUENCE IS WORSE THAN "A PASSIVE CHECK MISSES IT" — EXECUTED EVIDENCE, E-276-02, 2026-07-26.** Everything above describes a check that fails to *notice*. SE hit the sharper form: **the swallow disarms an assertion written INSIDE the swallowed region.** Its first AC-8 test asserted within a spy callback; the `AssertionError` was caught by `_reconcile_absent_games`' broad `except`, and the test failed pointing at the wrong cause. **It failed at all only because an append happened to sit after the assert — reordering two lines would have made it PASS while the property it tested was broken.**

**That is a different and worse claim than the one this idea was filed on.** Not "a test that does not look will not see," but **"a test that DOES look, at the right property, can be silently converted into a passing test."**

**⚠️ SCOPED — the disarm is REAL at every site but UNBACKSTOPPED at only four of the five, and that difference decides whether existing tests must be rewritten** *(CR, 2026-07-26; PM-verified in source at `game_loader.py`'s `except` → `return 1`)*:

| Site | An assertion raised inside it | Backstop |
|---|---|---|
| dedup sweep · game reconcile · exempt pre-plan · roster reconcile | eaten; run reports clean | **NONE — silently passes** |
| **player-line reconcile** | eaten by the same mechanism | **`return 1` → `LoadResult.errors == 1`**, and story-01 tests assert `errors == 0` **outside** the load, so it surfaces |

**The practical rule**: an assertion inside a callback reached from the four uncounted sites is unreliable and nothing at the call site says so; on player-line the existing outside assertion already catches it. **That is the difference between "these tests must be rewritten" and "already covered" — and it is why TN-12 prescribes the result-object spy on the game grain specifically.**

**⛔ HOW TO CHECK IT — the predicate is "invoked from within the swallowed region", NOT "nested"** *(CR's correction to PM's first formulation)*. Nesting is a cheap proxy that **over-flags**: a nested helper called from the test's own frame is perfectly reliable. The discriminating property is whether the enclosing callable is handed to `patch` / `side_effect`, or otherwise invoked by production code inside the `try`. **Mechanically checkable — enumerate the callables passed to patching, then look for `assert` inside those.** *(The nesting form would have flagged a safe test in `test_game_grain_reconcile.py`, and **a rule that over-flags teaches reviewers to discount its own signal** — a failure mode distinct from being wrong.)*

**A reviewer still cannot tell a disarmed assertion from a satisfied one by reading the test.** That part stands at every site.

**📌 Provenance, recorded because it is this epic's subject landing on the person cataloguing it.** PM wrote *"any assertion … from one of these five sites is unreliable **by construction**"* — over-strong, and **the fact refuting it was already in this file's own five-site table 25 lines above**, which names player-line as the ONLY counter. **Same shape as the AC-12/AC-6 pair PM had written into the closure record hours earlier**: a stronger claim and a weaker true one, agreeing in direction, the stronger one wrong. **Caught by CR executing the sweep, not by PM re-reading** — which is the detector that entry already names.

**⛔ AND E-276 SHIPPED THE ASYMMETRY INTO ITS OWN FIX — both halves MEASURED** *(CR at story 02 review, 2026-07-26)*. The epic added a required pre-upsert snapshot parameter to two grains. **The same wiring mistake fails with different VISIBILITY depending on which grain you make it in:**

| Grain | The mistake raises | What the operator sees |
|---|---|---|
| player-line | `KeyError` | `LoadResult.errors == 1` — **surfaced** |
| game | `TypeError` | swallowed, rolled back — **the run reports CLEAN** |

**Practical risk today is low** (the parameter is required, the sole caller passes it, the suite covers the path) **and that is not the point.** One epic, in one design pass, produced two grains whose identical failure mode is loud on one and silent on the other — **and neither outcome was chosen.** Both are downstream of which `except` block happens to sit above each call site. **So any future fix here must DECIDE the asymmetry, not merely add a counter to one site**; adding one counter would leave the same arbitrary split with a smaller numerator.

*(Kept in THIS idea rather than filed separately — see the anti-split note below, which this case tests exactly: the root cause is the same five swallow sites, and a separate idea would let a reader close the visibility gap on one grain and consider it done.)*

**It also sharpens — without changing — a ruling in E-276.** That epic classified a merge that *fails* rather than refuses as a compound residual, and reasoned that the productive closure was at the merge-failure end **because such a failure would be recurring and visible**. Recurring, yes. Visible through the channel we actually check, **no**. The ruling stands; its supporting assumption is narrower than stated.

## Rough Timing

No urgency from a known live incident, and **that is a statement about evidence rather than about safety** — nobody has checked whether collapses are currently failing in production, and the defect's whole shape is that the check everyone runs would not show it.

Promote when any of:
- Someone greps production logs for the dedup ERROR line and finds non-zero occurrences.
- A split identity surfaces on a coach-facing report — two rows for one human, each with part of a season.
- Any work touches `dedup_team_players`' error handling for another reason, since the fix is plausibly a one-line increment plus a test.

## Dependencies & Blockers

- [ ] None structural. The change is small; the open question is whether incrementing `errors` is the right disposition or whether it would make a load *fail* that today merely logs — a behavioural change on a path that runs during every report generation.

## Open Questions

- **Should a failed collapse increment `errors`, or does it need a separate counter?** `errors` currently gates callers' notion of a clean load. A dedup failure is real but is not the same class as a failed stat load, and conflating them could turn a cosmetic identity problem into a hard failure of report generation.
- **Are collapses failing today?** Unmeasured. This should be answered before designing anything — a log grep settles it.
- ~~**Is there a third channel that should carry it** — the reconcile result objects E-276 introduces, for instance — rather than either existing option?~~ **ANSWERED 2026-07-26 — NO, not for the roster grain as built** *(CR at E-276-03 review)*. `_reconcile_departed_roster`'s swallowed-exception branch returns a bare `RosterRetireResult()` whose defaults are **byte-identical to the sixth "nothing to decide" state** that story's own AC-3 defines. **So on the ONE grain whose wrapper swallows without an `errors` backstop, the new result record cannot tell a crash from a clean no-op either.** The third channel was this idea's most promising option and it **does not close the gap unaided** — any fix must give the crash path a *distinguishable state*, not merely add a record.

    **⛔ Deliberately NOT fixed in E-276-03, and the restraint is worth preserving.** `refused_by`'s membership was the subject of a **P1 at the second spec pass**, where three sources carried three different sets; inventing a sixth member mid-story to cover the crash path would have re-opened precisely that defect. SE documented the ambiguity at the site, CR confirmed the restraint was right, and **blast radius is nil today because the production call site discards the return.** *(This is the third mechanism producing "0 retired" on that grain — the shape TN-11 exists to close, arriving through the one path TN-11's enum does not model.)*
- ~~**Does the same swallow-without-count shape appear anywhere else** in the load path? The pattern was found by reading one except block; nobody has swept for siblings.~~ **RETIRED 2026-07-26 — this question was ALREADY ANSWERED by this idea's own body when it was written.** The five-site table above IS the sweep, and it was in the file from day one. The question survived beside its own answer for a day, and the two sit **40 lines apart in one short document**. *(Recorded rather than deleted: an Open Question that a document already answers is a live invitation to redo the work, and this one was about to be answered a second time — a reviewer proposed exactly this sweep on 2026-07-26. That is the cost, and it nearly landed.)*

## Notes

Surfaced at the close of E-276's roster-lock investigation: a code-reviewer asked whether a repeated collapse failure is actually surfaced to an operator, and software-engineer verified the answer in source. **Routed out of E-276 deliberately** — that epic's scope was held tight to the gate-population fix, and neither party proposed it ride along.

**⚠️ Deliberately filed as ONE idea, not two.** The `dedup_team_players` finding and the broader four-of-five maintenance-path observation are **one gap seen twice**, and splitting them would let a future reader fix the dedup site and consider the class closed.

**What is NOT in this idea, because it was IN E-276's scope and is written into that epic**: TN-11 prescribed *"the returned result object reports no errors"* as completion evidence on **every** grain, which is sound on player-line and **vacuous on game and roster** — a test author following it literally would have shipped an absence assertion a raised reconcile satisfies. That was a live spec defect and it was repaired in the epic. **This idea is the design question underneath it**, which neither reviewer ruled on: swallow-and-continue is deliberate for maintenance passes, so whether the *visibility* gap is wrong is genuinely open.

**Captured because it is the kind of item that dies for procedural reasons rather than on its merits**: it was raised while closing something else, which is the least likely moment for a finding to be written down. It is the second such item from that session.

Related: [[IDEA-188]] (a roster delete converting a refused fork into an executed merge) and [[IDEA-089]] (Tier 2 co-occurrence fork disambiguation) — all three sit on the `team_rosters` ↔ dedup coupling.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
