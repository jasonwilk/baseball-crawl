# E-259-02: Retire the season-aggregate write paths

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`DONE`

## Description
After this story is complete, nothing **writes or recomputes** `player_season_batting`/`player_season_pitching`. `canonical_recompute`, `ScoutingLoader._compute_season_aggregates`, and the player-dedup recompute path are removed, and `merge_player_pair`'s member-row **re-point** logic (in `_delete_or_repoint_season_rows`) is retired as dead-post-cutover.

> **DISPATCH CORRECTION (2026-07-12, PM — DE traced the surface; the story's file model was substantially STALE after E-256 relocations):**
> 1. **`_merge_season_rows` does NOT exist** — the real season-row handler is `_delete_or_repoint_season_rows` (Steps 6/7 of `merge_player_pair`). Its member-row RE-POINT half is dead post-cutover; its boxscore_only-season-row DELETE half stays for FK-safety until story 03 (Q2).
> 2. **The cascade DELETEs are at `src/reports/lifecycle.py:515-516` (`cascade_delete_team`), NOT `generator.py:2816-17`** — E-256 relocated them. They DELETE `player_season_*` on team deletion for FK-safety; **KEPT here, removal handed to story 03** (Q2 — a DELETE-for-FK-cleanup on a soon-dropped table is not an aggregate write).
> 3. **`_COMPLETENESS_RANK` (`:473`) is DEFERRED OUT of this story (Q3).** PM verified it is NOT a season/member guard — it is **per-game** conflict-resolution in `_delete_or_update_game_stats` (`:764-765`). It IS vestigial in production (column `stat_completeness` is `NOT NULL DEFAULT 'boxscore_only'` on `player_game_*` per migration 001, and NO `src/` writer sets `full`/`supplemented` on the per-game tables → the dup-wins branch is unreachable on real data), BUT its vestigial-ness is **independent of the E-259 season cutover**, the story mislabeled it a season guard, and removing it deletes `test_player_dedup.py`'s `full`-per-game-row dup-wins test (a schema-permitted behavior). Captured as a follow-up dedup-simplification idea, NOT bundled here.
> 4. AC-3's "tuples they build from" is not literal — `*_recompute_select()` return string constants, they do not build from the KEYS. The RETAIN outcome is still correct (see amended AC-3).

## Context
Story 01 made the readers query-time, so the stored tables have no reader and these writers produce dead rows. Technical Notes §7 enumerates the guards that collapse: `_merge_season_rows` dies **entirely** (not just its member-row half), `_COMPLETENESS_RANK` (`player_dedup.py:473`) with it, and `merge_player_pair`'s E-237 member-row re-point becomes dead code — because the mixed-provenance scope those guards defended **cannot exist** once no writer produces `full`/`supplemented` rows. These are three of E-237/E-253's hardest-won guards becoming unnecessary rather than merely dead.

## Acceptance Criteria
- [ ] **AC-1** (AMENDED — cascade DELETE relocation + Q2): Given the write paths, when this story is complete, then `canonical_recompute` (`src/db/season_aggregates.py`), `ScoutingLoader._compute_season_aggregates`, and the player-dedup recompute call are removed, and **no code WRITES or RECOMPUTES** `player_season_batting`/`player_season_pitching`. The FK-cleanup cascade DELETEs — relocated by E-256 to **`src/reports/lifecycle.py:515-516`** (`cascade_delete_team`), NOT `generator.py:2816-17` — are **RETAINED for FK-safety; their removal is handed to story 03** (which drops the tables). A DELETE-for-FK-cleanup on a soon-dropped table is not an aggregate write.
- [ ] **AC-2** (AMENDED — real function name + `_COMPLETENESS_RANK` deferred): Given `src/db/player_dedup.py`, when this story is complete, then `merge_player_pair`'s member-row **RE-POINT** logic in **`_delete_or_repoint_season_rows`** (NOT `_merge_season_rows`, which does not exist) is retired as dead-post-cutover (no writer can produce `full`/`supplemented` member rows to re-point); the boxscore_only season-row DELETE half of that handler stays for FK-safety until story 03 (AC-1/Q2). **`_COMPLETENESS_RANK` (`:473`) is NOT touched by this story** — DEFERRED per the Q3 ruling (it is per-game conflict-resolution, vestigial-by-convention but independent of the season cutover; follow-up idea).
- [ ] **AC-3** (AMENDED — KEYS clarification): Given `batting_recompute_select()`/`pitching_recompute_select()` **and the `BATTING_RECOMPUTE_KEYS`/`PITCHING_RECOMPUTE_KEYS` tuples**, when this story is complete, then all four are **retained** — only the DELETE+INSERT recompute *driver* (`canonical_recompute`) is removed, never the projection helpers or the key tuples. Correction: the `*_recompute_select()` builders return **string constants**; they do NOT "build from" the KEYS, and **story 01 reused the SELECT BUILDERS only, NOT the KEYS tuples** (it hand-maps unpacking to the reader's exact dict keys, since the KEYS carry extra columns — batting r/tb, pitching r/wp/bf — the reader must not return). The KEYS' only remaining live consumers are `aggregate_parity.py` + its test, **both deleted in story 04** — so the KEYS stay LIVE through story 02 and **ORPHAN in story 04** (handoff already recorded in story 01's History; story 04's dead-code sweep deletes/re-homes them).
- [ ] **AC-4**: Given the player-dedup flow, when this story is complete, then a merge still completes correctly without the season-aggregate recompute (the CLI/load-path dedup no longer needs to rebuild stored season rows, because there are none), verified by the existing dedup tests re-pointed as needed.
- [ ] **AC-5**: Given the full suite, when this story is complete, then it is green.

## Technical Approach
Remove the recompute driver but keep the projection helper (AC-3). The dedup path simplifies substantially — DE assesses whether `execute_collapse`/`plan_player_dedup` still need any post-merge season step (they should not). Be surgical about `merge_player_pair`: only the season-row re-point is dead; the player-row merge itself stays. Verify each removed guard against what it defended (the mixed-provenance scope) before deleting, per the twin-method-collapse lesson.

## Dependencies
- **Blocked by**: E-259-01 (readers must be query-time first)
- **Blocks**: E-259-03 (tables can only drop once nothing writes them)

## Files to Create or Modify
- `src/db/season_aggregates.py` (remove `canonical_recompute` driver; keep `*_recompute_select()` + the `*_RECOMPUTE_KEYS` tuples)
- `src/gamechanger/loaders/scouting_loader.py` (`_compute_season_aggregates` + its call)
- `src/db/player_dedup.py` (`_delete_or_repoint_season_rows` member-row **re-point** only — NOT `_merge_season_rows` [does not exist], NOT `_COMPLETENESS_RANK` [Q3-deferred]; keep the boxscore_only-DELETE half for FK-safety until story 03)
- **DELETE `tests/test_aggregate_parity.py`** (Q1 option a — its entire subject is recompute-vs-stored parity, which ceases to exist when `canonical_recompute` dies; story 04 then deletes only `aggregate_parity.py` SOURCE + `validate_plays_stats.py`). DE MUST confirm the file carries ONLY parity assertions before deleting — if any unrelated coverage lives there, port it.
- The affected dedup / scouting-loader test files (re-point as needed)
- **NOT** `src/reports/generator.py` (the cascade DELETEs relocated to `lifecycle.py` and are RETAINED per Q2 — story 03 removes them)
- **NOT** `src/reports/lifecycle.py` (cascade DELETEs kept for FK-safety; story 03's territory)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-259-03**: confirmation that no writer targets the stored tables, so the DROP is safe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests updated and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Keep the SUM projection helper (AC-3). Deleting it would break story 01's reader — the whole point of E-256 preserving it.
