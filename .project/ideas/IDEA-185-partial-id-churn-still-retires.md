# IDEA-185: Partial player_id Churn Still Hard-Deletes Live Stat Lines

## Status
`CANDIDATE`

## Summary

Even with E-276's health gate fixed, a **partial** GameChanger `player_id` churn still hard-deletes live per-player stat lines. With 9 prior lines and a fresh boxscore carrying 5 survivors plus 4 brand-new ids, the honest gate computes `comparable 5 >= 4.5` and permits, so the 4 churned lines are retired. Closing this needs a dedup-candidate signal (a same-game name-prefix check), not a tighter ratio and not an absolute cap.

## Why It Matters

A re-issued `player_id` for the same human is precisely the input `bb data dedup-players` exists to merge — the human has not left, GameChanger just gave them a new id. Retiring their line destroys real data that a merge would have preserved.

E-276 fixes the case where churn is total (zero overlap), because the gate then sees an empty intersection and refuses outright. Partial churn is the harder and arguably more common shape: a boxscore where most players keep their ids and a few are re-issued. The gate cannot distinguish "this player is gone" from "this player has a new id" using set arithmetic alone, because both look identical as ids.

The residual is stated explicitly in E-276's Technical Notes (TN-8) so that epic's prose does not imply the grain now refuses all churn. This idea is where the remainder lives.

## Rough Timing

No urgency **from a known live incident** — but note that is a statement about evidence, not about safety. Nobody has measured how often partial churn occurs in practice, so "no urgency" here means unmeasured rather than benign.

Promote when any of:
- A coach or the operator reports a player's stat line disappearing from a report between generations.
- Someone measures churn frequency against the live database and finds partial churn is not rare.
- IDEA-089 (Tier 2 co-occurrence fork disambiguation) is promoted — the same-game co-occurrence signal it would build is the natural instrument for this too, and doing both at once is much cheaper than doing either twice.

## Dependencies & Blockers

- [ ] E-276 must land first — this is the residual *after* that fix, and its behaviour is only well-defined once the gate is honest.
- [ ] Needs a decision on where the dedup-candidate signal lives. The retire currently runs **before** `dedup_team_players` by explicit design (dedup merges `player_id`s, so a reconcile running after it would diff canonical prior ids against raw payload ids). Any fix has to respect that ordering rather than reverse it.

## Open Questions

- What is the actual frequency of partial `player_id` churn in the live data? Nobody has measured it. This should be answered before designing anything — the answer determines whether this is a real defect or a theoretical one.
- Is the right instrument a name-prefix check against the same game's roster (cheap, reuses the existing dedup detection shape), or something stronger? Prefix matching alone cannot tell one human from two — that is exactly why `plan_player_dedup` refuses forks.
- Should a churn-suspected absence be *refused* (bias-to-refuse, leaving a stale row) or *deferred* to the dedup sweep that runs later in the same load? The second is more correct and more complex.
- Does the same shape apply to the roster grain, where a re-issued id also produces an absence?

## Notes

Surfaced during E-276 discovery, independently by data-engineer and software-engineer, and routed out of that epic deliberately — E-276's scope was held tight to the gate-population fix at the operator's explicit instruction.

Explicitly **not** the fix for this: an absolute per-game cap on player-line retirements. E-276's Non-Goals record why — with the gate honest a cap adds nothing to the total-churn case, and adding one would mask that epic's own regression tests the same way the roster cap currently masks the roster gate. A cap bounds the damage of a wrong decision; it does not make the decision right.

Related: [[IDEA-089]] (Tier 2 co-occurrence fork disambiguation) — same underlying signal.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
