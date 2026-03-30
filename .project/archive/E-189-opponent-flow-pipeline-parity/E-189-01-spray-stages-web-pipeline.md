# E-189-01: Add spray stages and gc_uuid resolution to web scouting pipeline

## Epic
[E-189: Opponent Flow Pipeline and Display Parity](epic.md)

## Status
`DONE`

## Description
After this story is complete, `run_scouting_sync` in `src/pipeline/trigger.py` will run gc_uuid resolution, spray chart crawl, and spray chart load after the main scouting crawl+load -- matching the CLI's behavior. Opponents synced via the admin UI will have spray chart data fetched and loaded without requiring CLI intervention.

## Context
The CLI (`bb data scout`) runs five stages: scouting crawl, scouting load, gc_uuid resolution, spray crawl, spray load. The web trigger (`run_scouting_sync`) only runs the first two. This means spray charts are never populated for opponents synced through the admin UI. The spray crawler requires gc_uuid to call the authenticated player-stats endpoint, so gc_uuid resolution must precede the spray crawl.

## Acceptance Criteria
- [ ] **AC-1**: After `run_scouting_sync` completes successfully, gc_uuid resolution has been attempted for the team (if gc_uuid was NULL and public_id is available)
- [ ] **AC-2**: After `run_scouting_sync` completes the main crawl+load successfully, the spray chart crawler runs for the team using the resolved (or pre-existing) gc_uuid
- [ ] **AC-3**: After the spray crawl succeeds, the spray chart loader runs and inserts spray chart data into the database
- [ ] **AC-4**: If the team has no gc_uuid (resolution failed or no public_id), the spray stages are skipped with an INFO log and the crawl_job is still marked "completed"
- [ ] **AC-5**: If the main crawl+load succeeds but the spray crawl or load fails, the crawl_job status remains "completed" (spray is additive enrichment, not gating) and the error is logged at WARNING level
- [ ] **AC-6**: The web pipeline stages mirror the CLI pattern per Technical Notes TN-1: gc_uuid resolution before spray crawl, spray load after spray crawl
- [ ] **AC-7**: If the main scouting crawl+load fails, spray stages are skipped entirely (matching CLI behavior at `src/cli/data.py` lines 383-390)

## Technical Approach
The implementation adds three stages to `run_scouting_sync` after the existing load phase (line ~492 in trigger.py). The pattern follows the CLI's `_scout_live` function in `src/cli/data.py:392-435`. The gc_uuid resolution uses the existing `resolve_gc_uuid` function from `src/gamechanger/resolvers/gc_uuid_resolver.py`. The spray crawler and loader use `ScoutingSprayChartCrawler` and `ScoutingSprayChartLoader` respectively.

Key constraint: spray stages must not change the crawl_job status from "completed" to "failed" -- they are additive enrichment. The main crawl+load result determines the job status; spray failures are logged but do not override a successful main result.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-189-02 (shares trigger.py)

## Files to Create or Modify
- `src/pipeline/trigger.py` -- add gc_uuid resolution + spray crawl + spray load stages to `run_scouting_sync`
- `tests/test_trigger.py` -- add tests for spray stages in scouting sync

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
