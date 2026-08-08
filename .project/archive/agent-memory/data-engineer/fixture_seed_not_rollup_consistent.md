---
name: fixture-seed-not-rollup-consistent
description: seed.sql was never rollup-consistent (its former player_season_* rows ≠ per-game SUM); E-259 stripped those rows + dropped the tables so the SPECIFIC divergence is retired, but the surviving lesson holds — exact-SUM tests (projection golden, query-time cutover) need the purpose-built parity_consistent.sql, NOT seed.sql
metadata:
  type: project
---

> **STATUS (E-259 DONE, 2026-07-12):** seed.sql's `player_season_*` INSERTs were STRIPPED and both tables DROPPED (E-259-03); the `aggregate_parity` guard was DELETED (E-259-04). The SPECIFIC stored-vs-SUM divergences below are now PRE-E-259 HISTORY — seed.sql no longer holds stored season rows, and season stats are query-time-derived from the per-game rows. The SURVIVING, still-live lesson (reconciled in "How to apply"): seed.sql is a query-OUTPUT characterization fixture, so exact-SUM tests use the purpose-built `parity_consistent.sql` instead.

**(PRE-E-259 HISTORY — the stored season rows described here were removed in E-259-03.)** `tests/fixtures/seed.sql` stored `player_season_batting`/`player_season_pitching` rows are NOT a literal column-by-column rollup of its `player_game_batting`/`player_game_pitching` rows. They were hand-authored to make the rate-stat QUERY assertions (BA/OBP ordering, K/9 ordering) come out right — the header's "totals match exactly" holds only for ab/h/bb, not the full SUM subset.

Verified divergences (TEAM_VARSITY, 2026-spring-hs, discovered during E-234 review 2026-06-12):
- Batting PLAYER_VARSITY_01: stored `doubles=1, sb=1` vs game-rows sum `0, 0`.
- Pitching PLAYER_VARSITY_01: stored `gp_pitcher=3, ip_outs=54, so=22` vs 4 game appearances (G1/G3/G5/G7) summing `ip_outs=69, so=26, count=4` — GAME_007's closing appearance was never absorbed into the season row.
- `games_tracked` is NULL in every stored season row (column omitted from all seed INSERTs) vs the loader's `COUNT(*)` recompute → guaranteed mismatch.
- Seed game-pitching rows have no `appearance_order` → any `gs`-via-appearance_order recompute yields NULL for all pitchers.

**Why:** seed.sql predates and is shared across many query tests; its job is exercising query OUTPUT, not aggregate-rollup integrity.

**How to apply (reconciled post-E-259):** Any exact-SUM test of the season projection or the query-time readers — the SURVIVING `tests/test_season_projection.py` (projection golden over `batting_recompute_select`/`pitching_recompute_select`) and `tests/test_season_query_cutover.py` (query-time `get_season_*` vs an independent per-game SUM oracle); the DELETED `aggregate_parity` guard was the pre-cutover form — MUST use the purpose-built `tests/fixtures/parity_consistent.sql`, where the per-game rows SUM to the expected season totals (every projected column incl. `games_tracked=COUNT(*)`, and `appearance_order`/`gs` for a multi-appearance pitcher). Do NOT mutate seed.sql to make it rollup-consistent — high blast radius on the report golden and existing OBP/K-9 ordering assertions. See [[etl-patterns]] for the projection column subset and the `gs` NULL-safe CASE.
