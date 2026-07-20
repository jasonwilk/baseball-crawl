# IDEA-158: A Zero-Completed-Games Payload Blocks the Game-Grain Retire — three interacting blocks, and the obvious fix is unguarded

## Status
`CANDIDATE`
<!-- Codex Phase 4 review of the E-267 epic diff, 2026-07-20 (P1 + P2). Triaged VALID, deliberately
     FILED rather than remediated — see "Why this was filed, not fixed". Do NOT treat the presence of
     a P1 label as a reason to fast-track it; the reasoning for deferring is the substance here. -->

## Summary
A prior-loaded completed game that later vanishes from GameChanger is never retired when the fresh schedule contains ZERO completed games. It keeps counting in W-L, recent form, and the freshness count. **Three blocks interact, and no one of them is wrong by itself** — which is why this is not a one-line fix:

1. **The crawler discards the array.** `src/gamechanger/crawlers/scouting.py:163-166` early-returns when `completed_games` is empty, so the full `games` array is never assigned to the result and is discarded.
2. **The loader returns before the reconcile.** `src/gamechanger/loaders/scouting_loader.py:186-191` returns at `if not boxscores`, ahead of the game-grain reconcile call at `:227`.
3. **The obvious fix is unguarded precisely here.** `boxscores_complete = fresh_completed_ids <= loaded_stream_ids` is **VACUOUSLY TRUE** when there are zero completed games (`∅ ⊆ anything`). The guard that exists to catch an incomplete redirect map therefore offers no protection in exactly the scenario a fix would create risk: threading the full array past the filter would expose genuinely-absent games to retirement with an empty redirect map.

**Blast radius of the naive fix** is same-perspective redirects specifically. Cross-perspective ones are independently protected — `merge_duplicate_game` unions `game_perspectives`, and the `_other_perspectives` refusal in `retire_absent_games` blocks a whole-game delete on a shared row.

## Companion finding (P2) — PREREQUISITE, not an optional extra
**No test covers the production zero-boxscore path.** The E-267-02 GAP-1 fixtures construct a `games=[]` / `boxscores≠{}` shape that production cannot emit. This was code-reviewer's own E-267-02 SHOULD FIX 4, resolved with an explanatory comment instead of a test — **and the P1 defect lives inside that annotated blind spot.**

**P2 must land before P1's control flow changes.** Changing a hard-delete control flow with no test exercising the shape you are changing it for is the wrong order, and this grain hard-deletes a game plus its full child surface.

## Why this was filed, not fixed
Recorded so a future reader does not mistake deferral for oversight:

1. **The guard is vacuous where the fix is needed** (block 3 above). The fix and its safety net fail in the same scenario.
2. **P2 first.** See above.
3. **It is the epic's own posture, not a violation of it.** E-267-04 AC-1c ruled that a boxscore-less crawl is a DEGRADED RE-SCOUT, and that retiring on its evidence is the delete-on-absence-of-evidence this epic exists to prevent. The same early return blocks both the roster and game grains; P1 only makes the consequence more visible, because with prior completed games N > 0 and the report renders (unlike the true-preseason case, where `_no_games_gate` suppresses it).
4. **Reachability: PLAUSIBLE BUT UNOBSERVED, with no identified mechanism** (api-scout probe — see below). The gap opens only when the fresh array has ZERO completed games while prior-loaded completed games exist, i.e. every prior game vanished or reverted at once (~30 simultaneous reversions for a full season). No evidence supports it and no mechanism producing it has been identified. A payload showing zero completed games for a team with a loaded season is itself a distrust signal, so refusing on it is correct behavior.

   **PREMISE CORRECTION — do NOT cite either AC-4 as reversion evidence.** An earlier version of this reasoning claimed "the epic already treats single-game reversion as real, both AC-4s guard it with tests." **That is FALSE.** E-267-02 AC-4 guards games that were NEVER completed (`game_status` absent / `null` / `"new"`); E-267-03 AC-4 is the reconcile-before-dedup ordering constraint. Neither is evidence about a COMPLETED game reverting. The deferral stands on the probe evidence below, not on that premise.

## Likely correct shape (not prescriptive)
An **offline operator command** in the `bb data merge-duplicate-games` mould, rather than a load-path change:
- It can derive the needed relationships from the DB directly, with no dependency on a redirect map built during a load.
- It puts a destructive decision behind an explicit `--dry-run` / `--execute` action rather than making a degraded crawl silently destructive.
- It matches the established precedent for repairing what the live path deliberately refuses to touch.

## api-scout probe result (2026-07-20) — RESOLVED, supersedes the earlier open question
The question was whether GameChanger can EMIT a zero-completed-with-prior-completed payload. **No evidence it can:**
- **Longitudinal probe** over 583 previously-completed games in a 6-20 day window: **zero reversions, zero genuine removals.**
- **15 additional team-seasons spanning 2019-2026: zero teams returning zero-completed.** A 2019 team still returns all 50 of its games.
- **Season rollover mints a NEW `public_id`** rather than draining the old one — so the intuition "the season ended and the array emptied" does not describe GC's behavior.
- **A missing team returns 404, not an empty 200** — so the absent-team case does not produce the shape either.

**Re-scored: the defect is real in the code, but the payload that would trigger it has no observed occurrence and no known mechanism.** That strengthens the case for the offline-operator-command shape above over any load-path change — there is no live pressure forcing a riskier fix.

## Notes
- Related: [[IDEA-154]] (per-perspective game retire — the other game-grain retire-coverage residual), [[IDEA-156]] (the `_completed_games_with_data` predicate gap that governs the N this defect inflates).
- Source: Codex Phase 4 epic review, 2026-07-20. Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.

---
Created: 2026-07-20
Last reviewed: 2026-07-20
Review by: 2026-10-18
