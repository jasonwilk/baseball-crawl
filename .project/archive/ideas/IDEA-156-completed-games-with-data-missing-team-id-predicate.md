# IDEA-156: `_completed_games_with_data` Lacks a `team_id` Predicate — stale rows can inflate coverage N, hold "Through {date}", and suppress the empty-report gate

## Status
`CANDIDATE`
<!-- Surfaced 2026-07-19 during E-267-03 round-2 AC verification. PM ruled uncovered rows are left
     untouched (correct bias-to-refuse, AC-1b) and flagged a dependency: the ruling assumed all
     coach-facing player-line reads are team_id-scoped. Code-reviewer swept all 12 modules reading
     `player_game_*` and FALSIFIED that assumption for exactly one reader. PRE-EXISTING code — NOT an
     E-267 regression; E-267 does not touch this function. -->

## Summary
`_completed_games_with_data()` in `src/reports/generator.py:597-616` returns `(most_recent_game_date, game_count)` by testing whether a game has any player-line data. Its two EXISTS subqueries scope by `(game_id, perspective_team_id)` only:

```sql
EXISTS (SELECT 1 FROM player_game_batting b
        WHERE b.game_id = g.game_id AND b.perspective_team_id = ?)   -- :606-607
OR EXISTS (SELECT 1 FROM player_game_pitching p
        WHERE p.game_id = g.game_id AND p.perspective_team_id = ?)   -- :610-611
```

There is **no `team_id` predicate**. It is the SOLE `player_game_*` reader lacking one — code-reviewer verified this by sweeping all 12 modules that read those tables (the other perspective-only predicates in `generator.py` read `plays` or `spray_charts`, not player lines).

## Why It Matters
Per the function's own docstring it feeds three coach-facing surfaces, so a row that satisfies the EXISTS check without being live data corrupts all three:

1. **The "Through {date} (N games)" freshness display** — CLAUDE.md mandates this as THE coach-facing freshness presentation ("coaches think in games, not sync timestamps"). `MAX(g.game_date)` can be held at a game with no live player data, so the report claims currency it does not have.
2. **The footer N-of-M coverage count** — a game stays counted in N when its only surviving rows for that perspective are stale.
3. **The N == 0 silent-empty-report gate (E-235 Phase 4b HIGH-1)** — **the worst of the three.** A stale row keeps `N > 0` and thereby SUPPRESSES the guard that exists precisely to catch a report with no real data. A residual that defeats a documented safety gate is worse than one that skews a displayed figure: the gate's whole job is to fail loudly in this situation.

Note the severity ordering: this is a PRESENCE/COUNT/DATE defect, not stat corruption. No stat number can be affected — all four value-bearing aggregates scope by both predicates (`get_season_batting` `src/api/db.py:501,503`; `get_season_pitching` `:569,571`; `get_pitching_workload` `:178-179`; `get_pitching_history`/`build_pitcher_profiles` `:308-309`).

## Reachability
Requires BOTH conditions together: (a) a prior `player_game_*` row whose `team_id` matches no block the fresh payload resolves (the E-267-03 AC-1b "uncovered row" state — arises when team resolution changes between runs, e.g. an opponent re-resolved to a different team row or a renamed opponent creating a new row), AND (b) the game having no other live rows for that perspective. Narrow, but **not construct-only** — do not dismiss it as theoretical.

## Scope Note
The fix is the predicate gap here, NOT the E-267-03 retire scope. Widening the player-line retire to cover uncovered rows would mean deleting on absence-of-evidence and reintroduces the false-delete hazard the whole epic exists to prevent — AC-1b carries an explicit "do NOT fix it that way" instruction. Adding `team_id` to both EXISTS subqueries is the candidate fix; before doing so, check what `team_id` value the caller should pass and whether any legitimate current behavior depends on the looser check (a report for a team whose rows carry an unexpected `team_id` would start reading as empty, which may be correct or may be a regression depending on the data).

## Notes
- E-267-03 SHOULD FIX 1 (log prior `team_id`s covered by no block, routed to SE) becomes more valuable in light of this: it is the only thing that would give an inflated N or a stale "Through {date}" a diagnostic trail back to its cause. Check whether it landed before costing this idea.
- E-267-05 documents the operator-facing symptom (a stale "Through {date}" has a known cause).
- Related: [[IDEA-154]] (per-perspective game retire — the other known retire-coverage residual from this epic).
- Source: E-267-03 round-2 AC verification, 2026-07-19. Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17
