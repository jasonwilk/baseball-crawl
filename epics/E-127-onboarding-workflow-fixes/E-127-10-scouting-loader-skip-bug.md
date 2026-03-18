# E-127-10: Scouting Loader Skips Completed Crawl Runs

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the scouting load step in `bb data scout` will correctly find and load data from crawl runs that have already been marked `completed` by the crawl step. Currently the load step silently skips all scouted teams because the query filters for `status = 'running'` but the crawl step has already transitioned runs to `completed` before the load step executes.

## Context
The `bb data scout` command runs a crawl-then-load pipeline. The crawl step (`ScoutingCrawler.scout_team()`) marks each run's status as `completed` when it finishes successfully. The load step then calls `_find_scouting_run()` in `src/cli/data.py` (line 304-309) which queries `scouting_runs WHERE status = 'running' AND last_checked >= ?`. Since the crawl step already set status to `completed`, this query returns zero rows and the load step silently skips every team. During live testing on 2026-03-18, the operator had to manually call `ScoutingLoader.load_team()` to get opponent data into the database.

This is a data pipeline bug that blocks the entire scouting load path -- no opponent stats reach the database through the normal `bb data scout` workflow.

## Acceptance Criteria
- [ ] **AC-1**: `_find_scouting_run()` matches scouting runs with `status IN ('running', 'completed')` (not just `'running'`), so the load step finds runs that are in-flight or already finished by the crawl step.
- [ ] **AC-2**: The log message on line 311 accurately reflects the query criteria (currently says "No running scouting run found" which will be misleading after the fix).
- [ ] **AC-3**: `bb data scout` end-to-end: after the crawl step completes, the load step successfully loads opponent data into the database without manual intervention.
- [ ] **AC-4**: A test verifies that `_find_scouting_run()` returns results for a scouting run with `status = 'completed'`.
- [ ] **AC-5**: `_load_all_scouted()` (line ~382) has the same `status = 'running'` bug -- fix its query to also match `'completed'` runs and update its log message. This is the multi-team `bb data scout` path; without this fix, `bb data scout` (without a specific team argument) silently skips all completed runs.

## Technical Approach
The core fix is in `src/cli/data.py`. Two functions have the same bug:

1. `_find_scouting_run()` (line 304-309): The SQL query's `status = 'running'` filter needs to be broadened to `status IN ('running', 'completed')`. The log message at line 311 should be updated (e.g., "No eligible scouting run found").

2. `_load_all_scouted()` (line ~382): Same `status = 'running'` filter on a different query. This is the multi-team path. Same fix: broaden to `status IN ('running', 'completed')` and update the corresponding log message.

**Timestamp format note**: The repo consistently uses ISO `T`-separator format throughout (`strftime('%Y-%m-%dT%H:%M:%fZ', 'now')` in SQL, `.strftime("%Y-%m-%dT%H:%M:%S.000Z")` in Python). Both sides match. Maintain this format when implementing -- do not switch to space-separator format.

Key file: `src/cli/data.py` (`_find_scouting_run()` and `_load_all_scouted()` functions).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` -- fix `_find_scouting_run()` and `_load_all_scouted()` queries and log messages
- `tests/test_cli_data.py` -- test that completed runs are found by both query paths

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
