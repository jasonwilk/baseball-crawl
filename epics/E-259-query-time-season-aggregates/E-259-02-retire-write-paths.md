# E-259-02: Retire the season-aggregate write paths

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`TODO`

## Description
After this story is complete, nothing writes `player_season_batting`/`player_season_pitching`. `canonical_recompute`, `ScoutingLoader._compute_season_aggregates`, the player-dedup recompute path, and the report-generator cascade DELETEs (`generator.py:2816-17`) are removed, and the guards that existed **only** to protect the stored tables — `_merge_season_rows` and `_COMPLETENESS_RANK` in `player_dedup.py`, plus `merge_player_pair`'s member-row re-point logic — are retired.

## Context
Story 01 made the readers query-time, so the stored tables have no reader and these writers produce dead rows. Technical Notes §7 enumerates the guards that collapse: `_merge_season_rows` dies **entirely** (not just its member-row half), `_COMPLETENESS_RANK` (`player_dedup.py:473`) with it, and `merge_player_pair`'s E-237 member-row re-point becomes dead code — because the mixed-provenance scope those guards defended **cannot exist** once no writer produces `full`/`supplemented` rows. These are three of E-237/E-253's hardest-won guards becoming unnecessary rather than merely dead.

## Acceptance Criteria
- [ ] **AC-1**: Given the write paths, when this story is complete, then `canonical_recompute` (`src/db/season_aggregates.py`), `ScoutingLoader._compute_season_aggregates`, the player-dedup recompute call, and the cascade DELETEs at `generator.py:2816-17` are removed, and no code writes `player_season_batting`/`player_season_pitching`.
- [ ] **AC-2**: Given `src/db/player_dedup.py`, when this story is complete, then `_merge_season_rows` and `_COMPLETENESS_RANK` (`:473`) are removed entirely, and `merge_player_pair` no longer carries member-row re-point logic (dead post-cutover).
- [ ] **AC-3**: Given `batting_recompute_select()`/`pitching_recompute_select()` **and the `BATTING_RECOMPUTE_KEYS`/`PITCHING_RECOMPUTE_KEYS` tuples they build from**, when this story is complete, then all four are **retained** — story 01's query-time SQL reuses the select builders and the KEYS tuples (for the projection and row unpacking) so exactly one SUM projection survives. (Only the DELETE+INSERT recompute *driver* is removed, not the projection helper or its key tuples. Note: the tuples' former drift-guard `test_diff_columns_track_shared_keys` dies with `aggregate_parity` in story 04 — story 01's reuse is what keeps them live, not orphaned exports.)
- [ ] **AC-4**: Given the player-dedup flow, when this story is complete, then a merge still completes correctly without the season-aggregate recompute (the CLI/load-path dedup no longer needs to rebuild stored season rows, because there are none), verified by the existing dedup tests re-pointed as needed.
- [ ] **AC-5**: Given the full suite, when this story is complete, then it is green.

## Technical Approach
Remove the recompute driver but keep the projection helper (AC-3). The dedup path simplifies substantially — DE assesses whether `execute_collapse`/`plan_player_dedup` still need any post-merge season step (they should not). Be surgical about `merge_player_pair`: only the season-row re-point is dead; the player-row merge itself stays. Verify each removed guard against what it defended (the mixed-provenance scope) before deleting, per the twin-method-collapse lesson.

## Dependencies
- **Blocked by**: E-259-01 (readers must be query-time first)
- **Blocks**: E-259-03 (tables can only drop once nothing writes them)

## Files to Create or Modify
- `src/db/season_aggregates.py` (remove `canonical_recompute` driver; keep `*_recompute_select()`)
- `src/gamechanger/loaders/scouting_loader.py` (`_compute_season_aggregates`)
- `src/db/player_dedup.py` (`_merge_season_rows`, `_COMPLETENESS_RANK`, `merge_player_pair` re-point)
- `src/reports/generator.py` (cascade DELETEs at ~:2816-17)
- The affected test files (dedup, season-aggregate, scouting-loader)

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
