# E-152-01: Schedule Opponent Seeder

## Epic
[E-152: Schedule-Based Opponent Discovery](epic.md)

## Status
`TODO`

## Description
After this story is complete, a standalone function will parse a team's `schedule.json` and `opponents.json` files, extract all unique opponents, and upsert them into the `opponent_links` table. Both "linked" opponents (those with a `progenitor_team_id` in opponents.json, bridgeable to a real GC team) and "name-only" opponents (just a typed name, no GC link) will be recorded. The function will be testable in isolation without requiring the full sync pipeline.

## Context
Currently, no code reads `schedule.json` for opponent discovery. The existing `OpponentResolver` makes live API calls to resolve opponents but may not cover future opponents that appear only in the schedule. This story builds the data-parsing and insertion logic as a standalone, testable unit. Story E-152-02 wires it into the sync pipeline.

The identifier mapping has been confirmed by API Scout: `pregame_data.opponent_id == opponents.root_team_id` (100% match across 54 opponents). Both are local registry keys, NOT canonical UUIDs. See Technical Notes "GC Identifier Mapping" section for the full mapping table.

## Acceptance Criteria
- [ ] **AC-1**: Given a team's `schedule.json` with N game events containing `pregame_data.opponent_id`, when the seeder runs, then `opponent_links` contains a row for each unique opponent (deduplicated by opponent identifier), with `our_team_id` set to the member team's ID.
- [ ] **AC-2**: Given an opponent that appears in both `schedule.json` and `opponents.json`, when the seeder runs, then the `opponent_links` row uses `opponent_name` from `opponents.json` (primary) with `schedule.json` `pregame_data.opponent_name` as fallback, `resolution_method=NULL`, and `resolved_team_id=NULL`. Resolution is deferred to `OpponentResolver` per Technical Notes "Division of Labor" section.
- [ ] **AC-3**: Given an opponent that appears in `schedule.json` but has no `progenitor_team_id` in `opponents.json` (or is absent from opponents.json entirely), when the seeder runs, then the `opponent_links` row has `opponent_name` set, `resolved_team_id` NULL, and `resolution_method` NULL (so it remains eligible for future resolution via `resolve_unlinked()`).
- [ ] **AC-4**: Given the seeder runs twice with the same input data, then no duplicate rows are created in `opponent_links` (upsert behavior per Technical Notes "Idempotency" section).
- [ ] **AC-5**: The seeder follows the identifier mapping and insertion path defined in Technical Notes "GC Identifier Mapping" section and the division of responsibility in "Division of Labor" section.
- [ ] **AC-6**: The seeder's upsert always updates `opponent_name` regardless of existing resolution state. For all other fields, writes are suppressed when the existing row has a non-NULL `resolution_method` (`'auto'`, `'follow-bridge'`, `'manual'`) -- those rows are protected from overwrite. Per Technical Notes "Division of Labor" section.
- [ ] **AC-7**: Schedule events without `pregame_data` or without `opponent_id` (e.g., practices, bye weeks) are skipped without error.
- [ ] **AC-8**: Given the schedule or opponents JSON file does not exist or is empty, when the seeder runs, then it returns 0 and raises no exception.

## Technical Approach
The seeder reads two JSON files for a given team, cross-references them per Technical Notes "Two Data Sources, One Pipeline Step" section, and upserts results into `opponent_links`. The identifier mapping is confirmed (see Technical Notes "GC Identifier Mapping"). The function accepts `team_id` (int), paths to the schedule and opponents JSON files, and a DB connection (matching Handoff Context), making it testable with fixture data.

Reference files:
- Schema: `/workspaces/baseball-crawl/migrations/001_initial_schema.sql` (opponent_links table, line ~384)
- Existing resolver patterns: `/workspaces/baseball-crawl/src/gamechanger/crawlers/opponent_resolver.py`
- Schedule crawler (data format): `/workspaces/baseball-crawl/src/gamechanger/crawlers/schedule.py`
- Game loader schedule reading (join key usage): `/workspaces/baseball-crawl/src/gamechanger/loaders/game_loader.py`

## Dependencies
- **Blocked by**: None
- **Blocks**: E-152-02

## Files to Create or Modify
- `src/gamechanger/loaders/opponent_seeder.py` (new -- main seeder logic)
- `tests/test_opponent_seeder.py` (new -- unit tests with fixture data)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-152-02**: A callable seeder function importable from `src/gamechanger/loaders/opponent_seeder.py`. Required interface: accepts `team_id` (int), path to schedule JSON, path to opponents JSON, and a DB connection. Returns the count of rows upserted (int). Raises exceptions on unrecoverable errors (e.g., malformed JSON, DB write failure) -- E-152-02 wraps the call in try/except for error isolation. Missing or empty JSON files are handled internally (returns 0, no exception).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The existing `OpponentResolver` uses a different approach (API calls for progenitor resolution). The schedule seeder is complementary -- it seeds from local cached data without making API calls.
- Practice events and other non-game events in schedule.json should be filtered out gracefully.
