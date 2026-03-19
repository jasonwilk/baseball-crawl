# E-127-06: Crawler Skips Placeholder Teams from Seed Data

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, the crawler's DB source path will skip teams with NULL or placeholder `gc_uuid` values instead of sending them to the GameChanger API (where they return HTTP 500). The YAML source path already has `REPLACE_WITH_` prefix guards; the DB source path needs an equivalent safety check.

## Context
When `bb data crawl --source db` runs after `bb db reset`, the seed data contains member teams with placeholder gc_uuids (e.g., `lsb-varsity-uuid-2026`). The DB team loader in `src/gamechanger/config.py` queries `SELECT ... FROM teams WHERE is_active = 1 AND membership_type = 'member'` with no filter on gc_uuid validity. The `gc_uuid or str(row["id"])` fallback produces nonsense IDs that hit the GC API and return 500 errors. The fix is defined in epic Technical Notes TN-6.

## Acceptance Criteria
- [ ] **AC-1**: Given a team with `gc_uuid IS NULL`, when `bb data crawl --source db` runs, then that team is skipped with a warning log message.
- [ ] **AC-2**: Given a team with a gc_uuid that does not match UUID format (e.g., `lsb-varsity-uuid-2026`), when `bb data crawl --source db` runs, then that team is skipped with a warning log message.
- [ ] **AC-3**: Given a team with a valid UUID-format gc_uuid, when `bb data crawl --source db` runs, then that team is processed normally.
- [ ] **AC-4**: The warning log message includes the team name and the reason for skipping (NULL gc_uuid or invalid format).
- [ ] **AC-5**: Tests cover NULL gc_uuid, placeholder gc_uuid, and valid gc_uuid scenarios.

## Technical Approach
The filter belongs in `load_config_from_db()` in `src/gamechanger/config.py`, either as a SQL `WHERE` clause addition (`gc_uuid IS NOT NULL`) or as a post-query Python filter. A UUID format validation (regex or `uuid.UUID()` parse) catches seed placeholders that aren't NULL but aren't real UUIDs either.

Key files to study: `src/gamechanger/config.py` (lines 200-213, `load_config_from_db()`), `data/seeds/seed_dev.sql` (placeholder gc_uuid values), `tests/test_config.py` (existing DB config tests).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/config.py` -- add gc_uuid validity filter in `load_config_from_db()`
- `tests/test_config.py` -- tests for placeholder/NULL gc_uuid filtering

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
