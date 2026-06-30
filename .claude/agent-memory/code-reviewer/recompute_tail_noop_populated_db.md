# Removing an early-return before a recompute/dedup tail: prove the no-op on a POPULATED DB, not just fresh

When a refactor removes an early-return that previously guarded a "rebuild-from-source" tail
(canonical_recompute DELETE+re-INSERT, dedup_team_players, or any aggregate recompute), a
fresh-DB characterization test is NECESSARY BUT NOT SUFFICIENT to prove the tail is a no-op.

## The trap (E-247-01, caught by Codex in Phase 4b after I missed it)
E-247-01 collapsed the loader twin methods and DROPPED the in-memory `if not crawl_result.boxscores:
return total` early-return, so the production path now ALWAYS runs the dedup → canonical_recompute →
commit tail, even on a zero-boxscore load.

My round-1 reasoning: "recompute over 0 new per-game rows produces 0 aggregates → no-op." This is
WRONG on a populated DB. `canonical_recompute(team, season)` DELETEs the boxscore_only aggregates
and re-INSERTs from ALL EXISTING per-game rows (not "0 new" rows). And the tail's `dedup_team_players`
runs first and can MERGE players (mutate per-game rows). The fresh-DB test
(`test_e247_in_memory_empty_boxscores_runs_tail_as_noop`) passed because fresh DB has 0 per-game rows,
so recompute writes nothing — but that case is exactly where the no-op is trivially true and proves nothing
about the real risk.

## Why it's not idempotent in general
`canonical_recompute` being the sole writer makes aggregates == recompute(per_game) ONLY WHEN nothing
mutated per-game rows since the last recompute. Reachable out-of-sync states in this repo:
- `bb data backfill-appearance-order` — CLAUDE.md explicitly says it leaves aggregates stale until a
  manual recompute. After a backfill, a boxscoreless refresh's recompute CHANGES stored aggregates.
- Pre-existing un-merged duplicate players — the tail's dedup MERGES them (data mutation) during what
  was a no-op refresh before.
Reachable trigger: re-scouting a previously-loaded opponent whose crawl returns 0 boxscores (transient
API issue / only-upcoming-games) → populated DB + zero-boxscore in-memory refresh.

## Review rule
When a diff removes/relaxes an early-return that sat BEFORE a recompute/dedup/rebuild tail:
1. Demand the characterization test seed PRE-EXISTING state (per-game rows + aggregates) and assert
   byte-identical/untouched after the now-unconditional tail — fresh-DB-empty is not enough.
2. Trace whether any path can leave per-game rows out of sync with aggregates (backfill, reconcile,
   manual ops). If yes, the unconditional recompute is NOT a no-op → behavior change.
3. Under a behavior-preserving / stat HARD gate, the conservative fix is to RESTORE the early-return
   (gate the tail on "was there anything to load this invocation"), not to argue idempotence.

Generalizes [[multi-scope aggregate tests]] and the status/flag lifecycle audit: a "no-op tail" claim is
only as good as the DB state the test seeds.
