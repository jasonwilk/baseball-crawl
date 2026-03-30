# E-188-01: Post-Load Orphan Cleanup in Report Generator

## Epic
[E-188: Eliminate Orphan Team Stubs from Report Generation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report generator will snapshot team IDs before the scouting load, identify orphan opponent team rows created during the load, query all game-dependent data, then delete the orphans and their dependent rows. New report generations will create zero net new orphan team rows in the `teams` table.

## Context
The report generator calls `ScoutingLoader.load_team()` which creates game rows with FK references to opponent team stubs. These stubs accumulate as junk (~30 per report). The loader pipeline cannot be modified to skip stub creation because season aggregates depend on game rows which depend on team FKs. Instead, the generator snapshots team IDs before/after the load and deletes the difference. The critical ordering insight (from SE consultation): game-dependent queries must run BEFORE the cleanup, since cleanup deletes the game rows those queries depend on.

## Acceptance Criteria
- [ ] **AC-1**: Given a report is generated for any team, when the report completes successfully, then zero new orphan team rows remain in the `teams` table (orphan = created during this load run, not the subject team).
- [ ] **AC-2**: Given a team row existed before the report load began and is referenced as an opponent in this report's boxscores, when cleanup runs, then that pre-existing team row is NOT deleted (snapshot-diff guarantees this).
- [ ] **AC-3**: Given cleanup encounters a database error, when the error occurs, then the report is still marked as `ready` (cleanup failure is non-fatal; error is logged as a warning).
- [ ] **AC-4**: Cleanup deletes dependent rows in FK-safe order per TN-1: Phase 1 deletes game-scoped data by `game_id` (per-game batting, per-game pitching, spray charts, games), Phase 2 deletes team-scoped data by orphan `team_id` (rosters, season stats, teams).
- [ ] **AC-5**: The opponent scouting flow (`ScoutingLoader.load_team()` called from `src/pipeline/trigger.py`) is unaffected -- no cleanup runs in that code path.
- [ ] **AC-6**: Game-dependent queries (record, recent form, freshness, runs avg) execute BEFORE the orphan cleanup, per the ordering in TN-1.
- [ ] **AC-7**: Tests cover: (a) cleanup removes orphan teams created during load, (b) pre-existing teams are preserved, (c) cleanup is non-fatal on error, (d) query-before-cleanup ordering is maintained.

## Technical Approach
Add a snapshot-and-diff cleanup to `generate_report()` in `src/reports/generator.py` per TN-1. The snapshot captures all `teams.id` values before `ScoutingLoader.load_team()` runs. After the load, a second snapshot identifies new team IDs. The diff (minus the subject team) gives the orphan set. The existing query block (batting, pitching, roster, record, recent form, freshness, runs avg, spray charts) already runs before rendering -- the cleanup inserts between the query block and the render step. Deletion follows FK-safe order per TN-1. The entire cleanup is wrapped in try/except with a warning log on failure.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-188-02 (reuses the orphan identification and FK-safe deletion logic)

## Files to Create or Modify
- `src/reports/generator.py` -- add snapshot before load, cleanup helper after queries
- `tests/test_report_generator.py` -- new or extended tests for cleanup behavior

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-188-02**: The FK-safe deletion order and orphan identification pattern. E-188-02 reuses this logic for the one-time CLI cleanup command. Consider extracting the shared deletion logic into a helper function.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The cleanup should log the count of deleted teams at INFO level for operator visibility.
- The `_record_uuid_from_boxscore_path` safety net in ScoutingLoader also creates stubs, but they overlap with GameLoader's stubs (same gc_uuid). The snapshot-diff captures both sources.
- The snapshot approach is simpler and more reliable than querying orphans from games table joins because it catches ALL team rows created during the load, regardless of how they were created.
