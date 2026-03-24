# E-152-02: Wire Opponent Discovery into Member Sync

## Epic
[E-152: Schedule-Based Opponent Discovery](epic.md)

## Status
`TODO`

## Description
After this story is complete, every member team sync (`run_member_sync`) will automatically run opponent discovery as part of the pipeline. The schedule opponent seeder from E-152-01 will execute after the schedule is crawled, populating `opponent_links` for all opponents on the schedule. If the existing `OpponentResolver` is not already in the sync pipeline, it will be wired in alongside the seeder so that both data sources (opponents.json and schedule.json) contribute to a complete `opponent_links` table.

## Context
The baseball coach was clear: "Discovery is a side effect of having a schedule, not a separate action." The schedule seeder built in E-152-01 is a standalone function. This story integrates it into the member sync pipeline so opponent discovery happens automatically without any manual intervention. The `OpponentResolver` is confirmed NOT in the sync pipeline (SE verified: `crawl.py` runs `OpponentCrawler` which fetches/caches data, but NOT `OpponentResolver` which makes live API calls to resolve opponents). This story must wire in both.

## Acceptance Criteria
- [ ] **AC-1**: Given a member team with a synced `schedule.json`, when `run_member_sync()` completes for that team, then `opponent_links` contains rows for all unique opponents from the schedule.
- [ ] **AC-2**: Both the schedule seeder and `OpponentResolver.resolve()` run as part of the sync pipeline, with the seeder executing BEFORE the resolver, per Technical Notes "Pipeline Execution Order" section. Only `resolve()` is called -- `resolve_unlinked()` is experimental and must NOT be wired in. A test asserts that both are called during `run_member_sync()` and in the correct order.
- [ ] **AC-3**: Given the sync pipeline runs for SB Freshman (team 89), then `opponent_links` contains a row for every unique opponent that appears in the team's schedule (not just "non-empty" -- the count must match the number of distinct opponents in `schedule.json`).
- [ ] **AC-4a**: The seeder is wrapped in try/except with WARNING-level logging. A seeder failure is non-fatal -- the pipeline continues.
- [ ] **AC-4b**: The resolver's `CredentialExpiredError` must NOT be swallowed -- it propagates up (signals dead auth, consistent with resolver's intentional re-raise design). All other resolver errors are handled internally per-opponent by the resolver itself.
- [ ] **AC-4c**: The `crawl_jobs` row is NOT marked as failed for non-auth discovery errors. Game loading and stat loading proceed normally after seeder/resolver regardless of discovery outcome.
- [ ] **AC-5**: Given the pipeline runs twice for the same team, then no duplicate `opponent_links` rows are created (idempotent end-to-end).
- [ ] **AC-6**: The `OpponentResolver` is invoked with a `CrawlConfig` filtered to only the syncing team, per Technical Notes "Existing OpponentResolver" section. A per-team sync must NOT trigger resolution for other member teams.

## Technical Approach
Wire the schedule seeder and `OpponentResolver` into `run_member_sync()` after crawl completes. The seeder must run before the resolver per Technical Notes "Pipeline Execution Order" section.

For path discovery: load `CrawlConfig` from DB (needed for OpponentResolver anyway) to get `config.season` (the season slug, e.g., `"2026-spring-hs"`). Query `teams WHERE id = team_id` for `gc_uuid`. Construct paths: `data/raw/{config.season}/teams/{gc_uuid}/schedule.json` and `opponents.json`. See Technical Notes "Data File Path Discovery" for why `config.season` must be used instead of `teams.season_year`.

For OpponentResolver: filter `config.member_teams` to just the syncing team before passing to OpponentResolver, per Technical Notes "Existing OpponentResolver" section. Without filtering, every per-team sync resolves ALL member teams.

Error isolation differs by component: the seeder is wrapped in try/except with WARNING-level logging (non-fatal). The resolver's `CredentialExpiredError` must propagate (signals dead auth) -- only non-auth resolver errors are handled internally per-opponent by the resolver itself. See AC-4a/4b/4c for the full error contract.

Reference files:
- Pipeline trigger: `/workspaces/baseball-crawl/src/pipeline/trigger.py`
- Schedule seeder: `/workspaces/baseball-crawl/src/gamechanger/loaders/opponent_seeder.py` (from E-152-01)
- Opponent resolver: `/workspaces/baseball-crawl/src/gamechanger/crawlers/opponent_resolver.py`
- Crawl runner: `/workspaces/baseball-crawl/src/pipeline/crawl.py`

## Dependencies
- **Blocked by**: E-152-01
- **Blocks**: None

## Files to Create or Modify
- `src/pipeline/trigger.py` (modify -- add opponent discovery step to `run_member_sync`)
- `tests/test_pipeline_trigger.py` (modify or create -- test that opponent discovery is called during sync)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The pipeline caller convention (`source` and `team_ids` parameters) is documented in CLAUDE.md Architecture section. Follow it when wiring new steps.
- AC-4a/4b/4c are important: opponent discovery is valuable but not critical-path. A seeder failure should not prevent game data from loading; a resolver auth failure must propagate.
