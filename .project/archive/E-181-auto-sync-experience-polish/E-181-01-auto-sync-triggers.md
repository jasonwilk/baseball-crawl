# E-181-01: Auto-Sync on Team Add and After Merge

## Epic
[E-181: Auto-Sync and Experience Polish](epic.md)

## Status
`DONE`

## Description
After this story is complete, adding a team or merging teams automatically triggers a background stat update on the resulting team. The operator no longer needs to manually click "Update Stats" after these operations. Flash messages confirm the auto-sync is running.

## Context
Currently, after adding a team the flash message says "Use the **Update Stats** button..." and after merging it says "Click Update Stats to load fresh data." Both require a manual follow-up action. This is the most common friction point for operators. The auto-sync pattern reuses the existing pipeline triggers (`run_member_sync` / `run_scouting_sync`) and the existing running-job guard.

## Acceptance Criteria

**Auto-sync on team add:**
- [ ] **AC-1**: When a new team is added via the confirm page POST handler, a background stat update is automatically enqueued using the appropriate pipeline trigger (`run_member_sync` for member teams, `run_scouting_sync` for tracked teams).
- [ ] **AC-2**: The flash message after team add confirms the auto-sync (e.g., "Team added. Stats updating in the background.") using E-178's established terminology.
- [ ] **AC-3**: If a `crawl_jobs` entry already exists and is running for the new team, the auto-sync is skipped (no duplicate job).

**Auto-sync after merge:**
- [ ] **AC-4**: When teams are merged, a background stat update is automatically enqueued on the kept team using the appropriate pipeline trigger.
- [ ] **AC-5**: The flash message after merge confirms the auto-sync (e.g., "Teams merged. Stats updating in the background.").
- [ ] **AC-6**: If a `crawl_jobs` entry already exists and is running for the kept team, the auto-sync is skipped.

**General:**
- [ ] **AC-7**: Both auto-sync triggers use the existing `run_member_sync` / `run_scouting_sync` functions from `src/pipeline/trigger.py`, routed by the team's `membership_type`.
- [ ] **AC-8**: Auto-sync failures do not prevent the team add or merge from completing. The background task fails independently; the user sees the team added/merged and can retry via "Update Stats".

**Tests:**
- [ ] **AC-9**: Tests verify that a background sync is enqueued after team add (both member and tracked).
- [ ] **AC-10**: Tests verify that a background sync is enqueued after merge.
- [ ] **AC-11**: Tests verify the running-job guard skips auto-sync when a job is already running.
- [ ] **AC-12**: No regressions in existing tests.

## Technical Approach
Both triggers follow the pattern described in TN-1: after the successful DB operation, check for a running job, then enqueue the appropriate pipeline trigger via FastAPI `BackgroundTasks`. The confirm page POST and merge POST handlers may not currently accept a `BackgroundTasks` parameter -- if not, one must be added to the function signature (FastAPI injects it automatically when declared). The flash messages replace the current "click Update Stats" text with confirmation that auto-sync is running. E-178 is an epic-level prerequisite: these handlers and flash messages are modified by E-178 first.

## Dependencies
- **Blocked by**: None (E-178 is an epic-level prerequisite, not a story-level dep)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` -- add auto-sync trigger after team insert in confirm handler; add auto-sync trigger after merge; update flash messages
- `tests/test_admin_teams.py` -- add tests for auto-sync on add, running-job guard
- `tests/test_admin_merge.py` -- add tests for auto-sync on merge, running-job guard

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The pipeline caller convention (`source="db"` AND `team_ids=[team_id]`) must be followed per CLAUDE.md Architecture section. Omitting either parameter silently processes the wrong set of teams.
- Flash messages must use E-178's terminology ("Stats updating", not "Syncing").
- The confirm page handler needs the team's `membership_type` to route to the correct pipeline. This is available from the form data or the just-inserted team row.
