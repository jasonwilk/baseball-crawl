---
name: fixture-seed-not-rollup-consistent
description: tests/fixtures/seed.sql season aggregates are NOT a literal SUM of its per-game rows; aggregate-parity tests need a dedicated rollup-consistent fixture
metadata:
  type: project
---

`tests/fixtures/seed.sql` stored `player_season_batting`/`player_season_pitching` rows are NOT a literal column-by-column rollup of its `player_game_batting`/`player_game_pitching` rows. They were hand-authored to make the rate-stat QUERY assertions (BA/OBP ordering, K/9 ordering) come out right — the header's "totals match exactly" holds only for ab/h/bb, not the full SUM subset.

Verified divergences (TEAM_VARSITY, 2026-spring-hs, discovered during E-234 review 2026-06-12):
- Batting PLAYER_VARSITY_01: stored `doubles=1, sb=1` vs game-rows sum `0, 0`.
- Pitching PLAYER_VARSITY_01: stored `gp_pitcher=3, ip_outs=54, so=22` vs 4 game appearances (G1/G3/G5/G7) summing `ip_outs=69, so=26, count=4` — GAME_007's closing appearance was never absorbed into the season row.
- `games_tracked` is NULL in every stored season row (column omitted from all seed INSERTs) vs the loader's `COUNT(*)` recompute → guaranteed mismatch.
- Seed game-pitching rows have no `appearance_order` → any `gs`-via-appearance_order recompute yields NULL for all pitchers.

**Why:** seed.sql predates and is shared across many query tests; its job is exercising query OUTPUT, not aggregate-rollup integrity.

**How to apply:** Any aggregate-parity / recompute-vs-stored test (e.g., the E-234-02 `aggregate_parity` guard, the Epic C cutover gate) MUST use its own purpose-built fixture where `player_season_*` is the exact SUM of `player_game_*` (every diffed column incl. `games_tracked=COUNT(*)`, and `appearance_order`/`gs` for a multi-appearance pitcher). Do NOT mutate seed.sql to make it rollup-consistent — high blast radius on Story-01-style golden tests and existing OBP/K-9 ordering assertions. See [[etl-patterns]] for the parity column subset and the `gs` NULL-safe CASE.
