# IDEA-189: A Failing Player-Dedup Collapse Is Invisible to `LoadResult.errors`

## Status
`CANDIDATE`

## Summary

`dedup_team_players`' except block logs an ERROR with a traceback and continues — but does **not** increment `result.errors`. So a persistently failing collapse is visible in logs and **invisible through `LoadResult.errors == 0`**, which is the channel this codebase treats as authoritative for "did the mechanism complete cleanly."

That is a **swallow-without-count**, and it diverges from the swallow-**and**-count pattern documented as deliberate elsewhere in the same loader, where `game_loader.py` catches broadly, logs ERROR, and returns 1 into `result.errors` precisely so a failure is not lost. `.claude/rules/testing.md` builds on that pattern: *the result object is the evidence, a spy is not.* Here the result object is not evidence.

**And it is a CLASS, not a dedup quirk.** Verified across all five swallow sites in the scouting load:

```
scouting_loader.py :318  dedup sweep            except -> logger.error    NO count
scouting_loader.py :432  game reconcile         except -> logger.error    NO count
scouting_loader.py :521  exempt pre-plan        except -> logger.error    NO count, returns None
                   :593  ...and its caller      WARNING "Roster retire SKIPPED"
scouting_loader.py :622  roster reconcile       except -> logger.error    NO count
game_loader.py     :679  player-line reconcile  result.errors += ...      <- the ONLY counter
```

**So a run in which the game reconcile, the roster reconcile, the exempt pre-plan AND the dedup sweep all failed still reports `LoadResult.errors == 0`.** Four of five maintenance-path failures are invisible to the result object.

**Note the inversion, because it changes how the gap should be described**: swallow-with-count is **not** a norm the other sites depart from. **It is the single exception**, and it happens to be the one grain `.claude/rules/testing.md` documents. Write it as *"only player-line counts,"* never as *"dedup deviates"* — the second implies four sites drifted from a standard, when the standard was never general.

## Why It Matters

An operator or a test checking the result object sees a **clean load** while a collapse fails on every run.

The concrete consequence is a **split identity that does not self-heal**: a component the planner keeps trying to merge and never merges leaves two `player_id`s for one human, each carrying part of a season. Nothing in the authoritative channel says so.

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
- **Is there a third channel that should carry it** — the reconcile result objects E-276 introduces, for instance — rather than either existing option?
- **Does the same swallow-without-count shape appear anywhere else** in the load path? The pattern was found by reading one except block; nobody has swept for siblings.

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
