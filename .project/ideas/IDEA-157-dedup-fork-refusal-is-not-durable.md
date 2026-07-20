# IDEA-157: `plan_player_dedup` Fork Refusal Is Not Durable — a refused ambiguity silently becomes an executed merge when the population shrinks

## Status
`CANDIDATE`
<!-- Surfaced 2026-07-20 by code-reviewer during E-267-04 round-3 review, explicitly recommended for
     CAPTURE rather than fixing in that story. Filed against the DEDUP PLANNER, not against E-267:
     the roster retire is one way to reach the state, not the cause. -->

## Summary
`plan_player_dedup` (`src/db/player_dedup.py`) refuses a "fork" — a stub prefix-matching two or more distinct fuller names — because it cannot tell which human the stub is. That refusal is a **judgment about a real ambiguity, but it is not recorded anywhere durable.** It is recomputed from the current population on every run, so the same ambiguity is refused today and silently EXECUTED tomorrow once the population drops to a pair.

Worked case: a fork is stub + `{John Smith, Janet Smith}`. Janet leaves the roster and her row is correctly retired. The next dedup pass sees stub + John only, no longer detects a fork, and merges the stub into John. But the ambiguity the planner originally refused was genuine — a roster departure says nothing about which person the stub referred to. The merge may conflate two people, and nothing in the system records that the planner ever had doubts.

## Why It Matters
The failure is silent and irreversible-ish: a merged pair loses the evidence it was ever ambiguous, so no later pass can re-refuse. The system's own earlier judgment — "this is genuinely ambiguous, do not merge" — is discarded by a population change unrelated to the ambiguity.

Severity is moderate, not high, and it should be filed honestly as such:
- Reaching the state does NOT require the E-267 roster retire. **Natural roster evolution reaches it anyway**: if Janet genuinely left, GameChanger drops her from the roster crawl, the fork becomes a pair, and dedup merges regardless. The retire only arrives there sooner.
- The path predates E-267-04 round 3 (it existed in round 2 as well). NOT introduced by that story.

## Framing for whoever picks this up
The useful framing is **durability of the refusal**, not "the roster retire causes a merge". Candidate directions:
- Persist a fork refusal (which stub, which candidate names, when) so a later pass can see the ambiguity was already flagged, even after the population shrinks.
- Or make the merge decision consult refusal history rather than only the current population.
- Note the tension: a durable refusal risks a permanently unmergeable stub if the ambiguity is later genuinely resolved. Whatever is built needs a way to CLEAR a refusal, not only record it. E-267-04's exemption design ran into the mirror of this — see its AC-2a/AC-8 notes and the "a refused fork member must stay retirable" reasoning in `src/db/reconcile_at_load.py` — where exempting fork members would have produced permanently unretirable roster rows.

## Notes
- Related: [[IDEA-089]] (Tier 2 co-occurrence fork disambiguation — the "decide the fork correctly" idea; THIS idea is the complementary "do not silently forget the fork was ever refused"). If IDEA-089 is ever promoted, these should be considered together — durable refusal is much less valuable if forks get resolved properly instead.
- E-267-04's exemption deliberately covers only EXECUTABLE `plan.collapses`, never `refused_forks`, because exempting a fork member would make it permanently unretirable. That decision is correct and this idea does not disturb it.
- Source: E-267-04 round-3 code review, 2026-07-20.

---
Created: 2026-07-20
Last reviewed: 2026-07-20
Review by: 2026-10-18
