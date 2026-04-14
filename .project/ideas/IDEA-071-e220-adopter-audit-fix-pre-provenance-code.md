# IDEA-071: E-220 Adopter Audit — Fix Pre-Provenance Code Paths

## Status
`PROMOTED`

## Summary
E-220 introduced `perspective_team_id` as an architectural invariant, but nobody walked the graph of existing consumers to adopt it. `_find_duplicate_game` was the first casualty (fixed in e27e6eb). A systematic audit found four more code paths still operating on the pre-provenance model.

## Why It Matters
Wrong is wrong regardless of severity. These code paths produce incorrect results — inflated counts, missed perspective partitioning, redundant work — even if the data-critical aggregation paths are already correct.

## Findings

### F-1: Admin delete confirmation counts (MEDIUM)
**`src/api/routes/admin.py:723-788`** — Six COUNT queries on stat tables use `game_id IN (games involving team)` without perspective filtering. Counts are wrong in both directions: overstated (includes other perspectives' rows about other teams) and understated (misses scouting rows from T's perspective in games T didn't play). The cross-perspective safety gate (lines 842-876) IS correct — this is purely the informational row counts the operator reads before confirming.

Affected lines: 724 (`player_game_batting`), 729 (`player_game_pitching`), 763 (`spray_charts`), 770 (`plays`), 776 (`play_events`), 781 (`game_perspectives`), 786 (`reconciliation_discrepancies`).

### F-2: Reconciliation summary aggregates across perspectives (LOW)
**`src/reconciliation/engine.py:1167-1172`** — `get_summary_from_db()` does `GROUP BY signal_name, category, status` without `perspective_team_id` filtering. Double-counts discrepancies for cross-perspective games. CLI-only (`bb data reconcile --summary`).

### F-3: Backfill discovery/update ignores perspective (LOW)
**`src/gamechanger/loaders/backfill.py:140-156, 220-228`** — Discovery query finds `(game_id, team_id)` with NULL `appearance_order` without partitioning by perspective. UPDATE uses `(game_id, player_id, team_id)` without perspective. In practice mostly harmless (cross-perspective UUIDs differ so each perspective's rows match only their own player_ids), but one perspective's rows may stay NULL until a matching boxscore file is found.

### F-4: Spray loaders lack game-level perspective gate (LOW)
**`src/gamechanger/loaders/spray_chart_loader.py` and `scouting_spray_loader.py`** — No `game_perspectives` check before loading spray data. Both rely on per-row `INSERT OR IGNORE` on UNIQUE. Data correctness preserved; unnecessary API calls / file reads for already-loaded perspectives. Compare with plays_loader.py:149 which does this correctly.

## Rough Timing
Next time we touch these files, or as a small cleanup epic. F-1 is the most visible (operator sees wrong numbers in the admin UI). F-2 through F-4 are correctness fixes that prevent drift.

## Dependencies & Blockers
- [x] E-220 (perspective provenance) — complete
- [x] E-221 (cleanup-detection mirror invariant) — complete
- [ ] None — all findings are fixable now

## Open Questions
- F-1: Should the counts reflect what _will_ be deleted (two-pass: perspective + anchor), or should they reflect "all rows in games this team participates in" as a broader impact number? The former is accurate; the latter is defensible as "here's everything in the blast radius." Decision needed before fixing.
- F-3: Is the backfill script expected to run again, or was it a one-time migration aid? If one-time, fixing it has no operational value.

## Notes
- Root cause: E-220 shipped provenance but didn't walk the graph of consumers. Same class of bug as the `_find_duplicate_game` fix (e27e6eb).
- The cleanup-detection mirror invariant added in E-221 (`data-model.md`) codifies the principle for DELETE surfaces but the same logic applies inverse-ly: "when you introduce a new architectural invariant, audit pre-existing code that could now use it."
- All data-critical paths (season aggregation, dashboard queries, dedup, merge, DELETE cascades) are already correct. These findings are exclusively in operator-facing informational code and pipeline optimization paths.

---
Created: 2026-04-13
Last reviewed: 2026-04-13
Review by: 2026-07-12
