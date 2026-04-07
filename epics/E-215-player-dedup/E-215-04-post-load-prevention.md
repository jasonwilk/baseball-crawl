# E-215-04: Post-Load Dedup Prevention in Scouting Pipeline

## Epic
[E-215: Fix Player-Level Duplicates from Cross-Perspective Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, the scouting pipeline will automatically detect and merge same-team player duplicates at two points: (1) inside `ScoutingLoader.load_team()` after boxscore loading but before season aggregation, and (2) in the pipeline orchestrators (`_scout_live` and `run_scouting_sync`) after spray chart loading completes. This two-hook approach prevents duplicates from accumulating after the initial cleanup (E-215-03) and handles re-contamination from the spray chart loader's player stub creation. The detection and merge functions from E-215-02 and E-215-03 are reused, scoped to the freshly-loaded team.

## Context
The root cause (GC assigning different UUIDs per perspective) cannot be fixed -- it is a property of the GameChanger API. The name-preference fix (E-215-01) prevents name degradation but does not prevent new duplicate player_ids from being inserted.

The scouting pipeline has multiple stages that create player rows:
1. `ScoutingLoader.load_team()` -- roster + boxscore loading (creates the primary duplicates)
2. Spray chart loading (runs AFTER load_team, creates player stubs via `_ensure_stub_player()`)

A single dedup hook inside `load_team()` is insufficient because the spray loader runs afterward and can re-create deleted duplicate player stubs from cross-perspective spray data. Two hooks are needed: one before aggregation (for clean season stats) and one after spray load (to catch spray-introduced stubs).

The plays pipeline (`bb data crawl --crawler plays` + `bb data load --loader plays`) runs independently of `bb data scout` and is NOT part of the standard scouting flow. Any duplicate stubs introduced by plays loading are cleaned up by the next `bb data scout` run's post-spray hook or by manual `bb data dedup-players --execute`.

## Acceptance Criteria
- [ ] **AC-1**: **Hook 1 (load_team)**: In `ScoutingLoader.load_team()`, a dedup sweep runs AFTER roster + boxscore loading and BEFORE season aggregate computation (`_compute_season_aggregates`). This ensures aggregates are computed on deduplicated game-level data.
- [ ] **AC-2**: **Hook 2 (post-spray)**: In both `_scout_live()` (`src/cli/data.py`) and `run_scouting_sync()` (`src/pipeline/trigger.py`), a dedup sweep runs AFTER spray chart loading completes. This catches any duplicate player stubs re-created by the spray loader.
- [ ] **AC-3**: Both hooks use `find_duplicate_players()` from E-215-02, scoped to the specific (team_id, season_id) being processed.
- [ ] **AC-4**: Any detected duplicate pairs are merged using `merge_player_pair()` from E-215-03.
- [ ] **AC-5**: Both hooks log the number of pairs merged (or "0 duplicates found") at INFO level.
- [ ] **AC-6**: Given a scouting load where a player appears from both roster (initial name, player_id X) and opponent boxscore (full name, player_id Y), after the full pipeline completes (including spray stages) only the canonical player_id remains in team_rosters and game/season stat tables. Spray_charts may still contain references to orphan stubs from cross-perspective spray data where the stub had no team_rosters entry (per TN-9); these show "Unknown" names and do not affect stat accuracy or report/dashboard display.
- [ ] **AC-7**: If either dedup sweep fails for any pair, the error is logged but does NOT fail the overall pipeline. Partial dedup is acceptable -- the manual `bb data dedup-players --execute` can clean up failures.
- [ ] **AC-8**: Test that simulates a scouting load producing a duplicate pair, verifies the Hook 1 sweep merges it automatically before aggregation.

## Technical Approach
Add a `dedup_team_players(db, team_id, season_id)` function to `src/db/player_dedup.py` that calls `find_duplicate_players()` with team_id/season_id filter, then calls `merge_player_pair()` for each pair. This function is called from two locations:

**Hook 1**: Inside `ScoutingLoader.load_team()`, after `_load_boxscores()` returns and before `_compute_season_aggregates()`. Uses `manage_transaction=False` since the scouting loader's connection has an implicit transaction.

**Hook 2**: In `_scout_live()` (after the spray load step completes, before `raise SystemExit`) and in `run_scouting_sync()` (after `_run_spray_stages()` returns). These orchestrators own their DB connections, so `manage_transaction=True` is appropriate here.

Both hooks are wrapped in try/except so failures don't break the pipeline.

## Dependencies
- **Blocked by**: E-215-01 (name-preference upsert), E-215-02 (detection query -- directly called by both hooks), E-215-03 (merge function)
- **Blocks**: None

## Files to Create or Modify
- `src/db/player_dedup.py` (MODIFY -- add `dedup_team_players()` scoped function)
- `src/gamechanger/loaders/scouting_loader.py` (MODIFY -- Hook 1: call dedup after boxscore loading)
- `src/cli/data.py` (MODIFY -- Hook 2: call dedup after spray load in `_scout_live`)
- `src/pipeline/trigger.py` (MODIFY -- Hook 2: call dedup after spray stages in `run_scouting_sync`)
- `tests/test_player_dedup.py` (MODIFY -- add prevention integration test)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-215-05**: All implementation is complete. E-215-05 reads the epic Technical Notes and completed story artifacts to codify patterns in the context layer.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Hook 1 uses `manage_transaction=False` (per E-215-03 AC-1) since the scouting loader's connection may have an implicit transaction open.
- Hook 2 uses `manage_transaction=True` since the orchestrator functions own their connections and are outside any implicit transaction at the post-spray point.
- **Expected behavior: merge-every-run cycle.** After a merge deletes duplicate player_id X, the next scouting crawl will re-encounter X from the GC roster endpoint and re-create it. The Hook 1 sweep will re-merge it. This cycle is expected and harmless -- stats are always correct because dedup runs before aggregation. If the cycle proves noisy in operator logs, a `player_aliases` table (mapping deleted IDs to canonical) can be added in a future epic to prevent re-creation entirely.
- **Plays pipeline**: The plays loader (`bb data crawl --crawler plays` + `bb data load --loader plays`) runs independently of `bb data scout` and `run_scouting_sync`. It is NOT wired into these orchestrators. Any duplicate stubs introduced by plays loading are cleaned up by the next `bb data scout` run's Hook 2 sweep or by manual `bb data dedup-players --execute`.
