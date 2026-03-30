# E-189-02: Auto-scout opponents resolved during member sync

## Epic
[E-189: Opponent Flow Pipeline and Display Parity](epic.md)

## Status
`DONE`

## Description
After this story is complete, `_discover_opponents()` in `src/pipeline/trigger.py` will trigger scouting for opponents that were newly resolved during the discovery phase. When a member team syncs and the resolver auto-matches opponents to GC teams, those opponents will be scouted automatically -- eliminating the need for the operator to manually click "Sync" on each one.

## Context
`_discover_opponents()` runs the schedule seeder and `OpponentResolver.resolve()` after a member team sync. The resolver successfully auto-resolves opponents via progenitor_team_id and POST /search fallback, writing to `opponent_links` and calling `finalize_opponent_resolution()`. But the function never enqueues scouting for them. Auto-scout exists only in admin HTTP routes (manual connect + search resolve via BackgroundTasks). Verified 2026-03-29: Freshman Grizzlies sync resolved 7 opponents, 3 were never scouted.

## Acceptance Criteria
- [ ] **AC-1**: After `_discover_opponents()` completes resolution, opponents whose `resolved_at` timestamp is >= the sync cycle start time AND whose resolved team has `public_id IS NOT NULL` AND that pass the freshness filter in AC-3 are scouted by calling `run_scouting_sync`
- [ ] **AC-2**: Each auto-scouted opponent gets a `crawl_jobs` row created (sync_type='scouting_crawl') so the admin UI shows "Syncing..." status during the scout
- [ ] **AC-3**: Opponents that already have a crawl_job with status 'running' (any age) or 'completed' within the last 24 hours are skipped to avoid concurrent or redundant work
- [ ] **AC-4**: Auto-scout runs sequentially within `_discover_opponents()` per Technical Notes TN-2 (no BackgroundTasks -- already in a background context)
- [ ] **AC-5**: If auto-scout fails for one opponent, it logs the error and continues to the next opponent (does not abort the discovery phase)
- [ ] **AC-6**: After each `run_scouting_sync` call returns, check the crawl_job status. If the job was marked 'failed' with an error message indicating auth failure (e.g., contains "Auth refresh failed" or "Credential expired"), stop further auto-scout attempts for remaining opponents. (`run_scouting_sync` catches all exceptions internally and never re-raises, so auth failure must be detected via the crawl_job row.)

## Technical Approach
Record the current UTC timestamp before the resolver runs. After the resolver completes in `_discover_opponents()`, query `opponent_links` for rows where `resolved_at >= sync_start_time` and the resolved team has `public_id IS NOT NULL`, excluding teams with a `crawl_jobs` row in status 'running' (any age -- matching admin route's `_has_running_job()` behavior) or 'completed' within the last 24 hours. For each qualifying opponent, create a `crawl_jobs` row (`INSERT INTO crawl_jobs (team_id, sync_type, status) VALUES (?, 'scouting_crawl', 'running')`) and call `run_scouting_sync` directly with the new crawl_job_id (not via BackgroundTasks -- already in a background context). The `_discover_opponents` function signature does not need to change -- it already has access to `db_path` and `crawl_job_id` context.

## Dependencies
- **Blocked by**: E-189-01 (shares trigger.py -- must be staged first)
- **Blocks**: E-189-05

## Files to Create or Modify
- `src/pipeline/trigger.py` -- extend `_discover_opponents()` to trigger scouting after resolution
- `tests/test_trigger.py` -- add tests for auto-scout behavior

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
