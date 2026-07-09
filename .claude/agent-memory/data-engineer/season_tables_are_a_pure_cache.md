---
name: season-tables-are-a-pure-cache
description: player_season_* are a pure derived cache post-E-239 (zero full/supplemented writers, zero such rows live) — DROP is safe iff zero member rows; verified for E-259 cutover
metadata:
  type: project
---

Post-E-239, `player_season_batting` / `player_season_pitching` are a **pure derived cache** of `player_game_*`: the ONLY INSERT sites are `src/db/season_aggregates.py:250,310`, and both hardcode `'boxscore_only'`. No writer of `full` / `supplemented` provenance survives anywhere in `src/` or `scripts/`. The live `data/app.db` (verified 2026-07-09) holds 67 batting + 48 pitching rows, **100% `boxscore_only`**.

**Why:** this is the load-bearing precondition for the E-259 query-time cutover. Because the tables are 100% derivable from `player_game_*`, dropping them cannot lose data and rollback is just `git revert` + re-run `canonical_recompute` — no backup restore needed. But `full`/`supplemented` rows would be IRRECOVERABLE (the member `season_stats_loader` that produced them was deleted in E-239, and GC's season-stats endpoint is Forbidden for non-owned teams). The `NOT EXISTS` provenance guard in `canonical_recompute` is therefore **inert today** — it protects rows that no longer exist and can never be recreated.

**How to apply:** any DROP or destructive rewrite of `player_season_*` MUST be preceded by an operator preflight asserting
`SELECT COUNT(*) FROM player_season_batting WHERE stat_completeness <> 'boxscore_only'` = 0 (and same for pitching).
Green ⇒ the DROP is data-lossless. Non-zero ⇒ STOP, those rows are irrecoverable.

Two consumer facts that matter for the cutover:
- `generator.py::_query_batting/_query_pitching` (`src/reports/generator.py:399,441`) read the stored rows with **no `perspective_team_id` filter and no `stat_completeness` filter** — the stored rows already embody the perspective scoping that `canonical_recompute` applied at write time. A query-time replacement MUST add `perspective_team_id = team_id` explicitly or opponent-perspective rows double-count. This is the #1 cutover bug risk.
- Query-time derivation is free: measured **0.046 ms/team** (index-driven via `idx_pgb_perspective_game`, no table scan) vs 0.004 ms for the stored read. A report touches 1-2 teams.

Mitigation if the preflight ever comes back non-zero: **refuse the cutover**, do not archive. A frozen archive table is a stale-data trap dressed as safety — nothing reads or refreshes it, but it looks authoritative. A member row appearing at all would mean a writer we believe deleted has resurrected; stop and understand that.

Adjacent empirical fact (2026-07-09, same DB): `SELECT COUNT(*) FROM player_game_pitching WHERE appearance_order IS NULL` = 0, and `game_loader.py:1065,1533` populates the column on every load. `bb data backfill-appearance-order` is **dead three times over**: (1) no NULL rows to fix; (2) no writer can produce a new NULL; (3) `src/gamechanger/loaders/backfill.py:28` sets `_DATA_ROOT = data/raw` and builds `root / season_id / teams|scouting / ...`, but the on-disk legacy trees use the RETIRED suffixed-season taxonomy (`data/raw/2026-spring-hs/`) while the DB's `season_id` is the year-only `2026` — so `data/raw/2026/` does not exist and the path never resolves, even where the JSON bytes are on disk. It no-ops on THIS machine, not just fresh ones. (CLAUDE.md still documents it as live.) The taxonomy mismatch is another leaf of the cross-season machinery the user wants ripped out at the root.

Related: [[fixture_seed_not_rollup_consistent]], [[season_aggregate_writers]] (its "three divergent writers" finding is now reduced to one — ScoutingLoader and the dedup path both delegate to `canonical_recompute`).
