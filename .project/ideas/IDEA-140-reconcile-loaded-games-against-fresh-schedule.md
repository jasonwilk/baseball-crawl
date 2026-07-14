# IDEA-140: Reconcile Loaded Games Against the Freshly-Fetched Schedule (retire/redirect removed or rescheduled games)

## Status
`CANDIDATE`

## Summary
The scouting/report load pipeline is ACCUMULATE-ONLY. When the operator re-scouts the same team over time (e.g. runs a report now, then again a week later), teams/games/players/stats dedup and upsert correctly for the common case, and new games are picked up. But there is NO reconciliation pass for a game that DISAPPEARED or MOVED on GameChanger between runs. Add a reconciliation pass that, for a given team+season, compares the currently-loaded game set against the freshly-fetched schedule and retires (removed games) or redirects/merges (rescheduled games) the affected rows.

## Why It Matters
Reports are the sole coaching surface, and opponent season aggregates derive at query time from `player_game_*` (`get_season_batting` / `get_season_pitching`). A stale or duplicated game silently corrupts those aggregates:

- **Rescheduled game (the practical case — rainouts are common in HS/travel baseball):** `_find_duplicate_game` (`src/gamechanger/loaders/game_loader.py:990-1197`) keys on `game_date` + unordered team pair. If a game moves to a NEW date, the new date does not match the old row, so the second run INSERTS a new game row at the new date while the OLD-date row persists → the same real game is counted TWICE in that opponent's season aggregates, inflating the numbers.
- **Removed game:** if a game is deleted on GameChanger, its `games` row + `player_game_*` stat rows persist as STALE — nothing retires them. The only deletion during generation is `_cleanup_orphans` (`src/reports/generator.py:2143-2161`), which deletes orphan TEAMS this run created, never games.
- **Existing tooling does not cover this:** `bb data merge-duplicate-games` (`src/db/game_merge.py`) only merges cross-perspective TWINS on the SAME date — it will not detect a reschedule that changed the date, nor a removed game.

The corruption risk grows with the gap between runs and during rainout-prone stretches. This is a data-fidelity gap in the reports-first product, and it directly undercuts the "Always Get Closer to Byte-Identical Play Ingestion" north star for season-level aggregates.

## Rough Timing
Not urgent — low-frequency but real. Capture now; promote when the pain is felt (an actual inflated/stale opponent aggregate is observed) or as a natural follow-on to the dedup family (E-215/E-216/E-261). Rainout-prone stretches with repeated re-scouting of the same opponent are the most likely trigger.

## Dependencies & Blockers
- [ ] None hard-blocking. Builds naturally on the existing dedup lineage (E-215/E-216 player/game dedup, E-261 cross-perspective) and the canonical `merge_duplicate_game` seam.
- [ ] A decision on whether this runs automatically inside `generate()` or as a `bb data` operator-maintenance pass (see Open Questions) should precede epic scoping.

## Open Questions
- How to distinguish a genuinely REMOVED game from one that is merely not-yet-final or postponed (still on the schedule but without a final)? Retiring a postponed game that later resumes would be wrong.
- Hard-delete stale rows vs. soft-retire (a retirement marker/flag)? Soft-retire preserves auditability but adds schema/query surface.
- Does this run inside `generate()` automatically (every report re-scouts against the live schedule), or as a discrete `bb data` operator-maintenance pass? Precedent favors the `bb data` operator-maintenance-pass pattern (`bb data reconcile`, `merge-duplicate-games`, `backfill-game-dates`).
- How to corroborate a RESCHEDULE match so a genuinely different game is not wrongly merged? Date-alone is exactly what fails here; match a moved game by team-pair + score/play-count corroboration (mirroring the `is_offline_same_game` bias-to-refuse corroboration in `game_merge.py`), then merge-or-retire via the canonical `merge_duplicate_game` seam.

## Notes
- Surfaced 2026-07-14 from an operator question about re-scouting the same team over time, via a read-only trace by the main session.
- Natural home: the existing dedup/reconciliation family — `merge_duplicate_game` + `is_offline_same_game` (`src/db/game_merge.py`), `_find_duplicate_game` (`src/gamechanger/loaders/game_loader.py`), the `bb data` operator-maintenance passes. Related lineage: E-215/E-216 (player/game dedup), E-261 (cross-perspective game-dedup fidelity), and the query-time season-aggregate readers `get_season_batting` / `get_season_pitching` (E-259) that a duplicate game inflates.
- Related ideas: [[IDEA-089]] (terminal co-occurrence fork disambiguation — sibling in the dedup family). Also note IDEA-134 (play-level cross-perspective dup) in the v2/data-integrity backlog.

---
Created: 2026-07-14
Last reviewed: 2026-07-14
Review by: 2026-10-12 (suggest 90 days from created)
