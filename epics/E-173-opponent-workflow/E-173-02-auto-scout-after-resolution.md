# E-173-02: Auto-Scout After Resolution

## Epic
[E-173: Fix Opponent Scouting Workflow End-to-End](epic.md)

## Status
`TODO`

## Description
After this story is complete, resolving an opponent in the admin UI (via search or manual connect) automatically triggers a scouting sync in the background. The operator no longer needs to run `bb data scout` manually after resolution. A `crawl_jobs` row is created for tracking, and `run_scouting_sync` is enqueued as a FastAPI `BackgroundTask`.

## Context
Currently, after resolving an opponent, the operator must manually run `bb data scout` from the CLI to fetch scouting data. This is a friction point that breaks the "resolve and see stats" promise. Since `run_scouting_sync` in `src/pipeline/trigger.py` already handles the full scouting pipeline (crawler + loader), we just need to wire it as a BackgroundTask from the resolution handlers.

## Acceptance Criteria
- [ ] **AC-1**: After `resolve_opponent_confirm` (search resolve) succeeds and the resolved team has a non-null `public_id`, a `crawl_jobs` row is created and `run_scouting_sync` is enqueued as a `BackgroundTask`.
- [ ] **AC-2**: After `connect_opponent` (manual connect via POST) succeeds and the resolved team has a non-null `public_id`, a `crawl_jobs` row is created and `run_scouting_sync` is enqueued as a `BackgroundTask`.
- [ ] **AC-3**: If the resolved team's `public_id` is null (e.g., connected by UUID only), the auto-scout is skipped with a log warning. No error is raised.
- [ ] **AC-4**: The flash message after resolution includes a note about the auto-scout: e.g., "Linked to [team name]. Stats syncing in the background."
- [ ] **AC-5**: The `crawl_jobs` row uses `sync_type = 'scouting_crawl'` (consistent with existing scouting sync pattern in `src/pipeline/trigger.py`).
- [ ] **AC-6**: Tests verify that `background_tasks.add_task` is called with `run_scouting_sync` after resolution, and that it is NOT called when `public_id` is null.

## Technical Approach
The admin resolve handler already has access to `BackgroundTasks` via FastAPI dependency injection. The connect handler may need `BackgroundTasks` added as a parameter. The `crawl_jobs` row creation follows the same pattern as the admin sync route (admin.py ~line 2305-2315). The `run_scouting_sync` function in `src/pipeline/trigger.py` handles its own DB connection, auth refresh, and status tracking.

## Dependencies
- **Blocked by**: E-173-01 (the `finalize_opponent_resolution()` return dict provides `public_id` needed to decide whether to trigger scouting)
- **Blocks**: E-173-03

## Files to Create or Modify
- `src/api/routes/admin.py` -- add BackgroundTasks parameter to `resolve_opponent_confirm` and `connect_opponent` handlers; create `crawl_jobs` row and enqueue `run_scouting_sync`; update flash messages
- `tests/test_admin_resolve.py` -- test auto-scout trigger for search resolve path
- `tests/test_admin_connect.py` -- test auto-scout trigger for manual connect path

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The auto-resolver (`OpponentResolver.resolve()`) does NOT get auto-scout wiring in this story. The auto-resolver runs during `run_member_sync`, which is itself a background task -- nesting background tasks would be complex and the resolver may process many opponents in a batch. Auto-scout from the resolver is a potential future enhancement.
- The `run_scouting_sync` function creates its own DB connection and refreshes auth eagerly, so it is safe to run as a fire-and-forget background task.
