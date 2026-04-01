# E-197-04: Data Migration for Existing Mis-Tagged season_id Rows

## Epic
[E-197: Derive season_id from Team Context](epic.md)

## Status
`TODO`

## Description
After this story is complete, all existing database rows for the Lincoln Rebels 14U team (team_id 126) and any opponents scouted through it will have their season_id corrected from `2026-spring-hs` to `2025-summer-usssa`. A new season row for `2025-summer-usssa` will exist in the `seasons` table. This migration runs at app startup via `apply_migrations.py`.

## Context
The Rebels 14U (a 2025 summer USSSA team) was crawled under the `2026-spring-hs` directory and all 92 games plus associated data were tagged with the wrong season_id. Opponents scouted through the Rebels 14U scouting pipeline may also carry the wrong season_id. This migration corrects all existing data. Going forward, the loader changes in E-197-02 and E-197-03 prevent future mis-tagging.

This migration can be developed and applied independently of the loader changes (stories 02/03). It corrects existing data; the loader changes prevent new wrong data.

## Acceptance Criteria
- [ ] **AC-1**: Migration file `migrations/011_fix_season_id_rebels_14u.sql` exists and is idempotent (safe to run multiple times).
- [ ] **AC-2**: The migration begins with `PRAGMA foreign_keys=ON;` to ensure FK enforcement during UPDATEs.
- [ ] **AC-3**: A USSSA program row is created (INSERT OR IGNORE): `program_id='rebels-usssa'`, `program_type='usssa'`, `name='Lincoln Rebels'`. Team 126 is assigned to it: `UPDATE teams SET program_id = 'rebels-usssa' WHERE id = 126 AND program_id IS NULL`. This ensures the derivation utility produces `2025-summer-usssa` for this team.
- [ ] **AC-4**: A `seasons` row for `2025-summer-usssa` is created (INSERT OR IGNORE) BEFORE any UPDATE statements (FK prerequisite).
- [ ] **AC-5**: The migration discovers all affected team_ids using a SQL CTE: `{126} UNION SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126`. This set is used in all subsequent UPDATE WHERE clauses.
- [ ] **AC-6**: All `games` rows where (home_team_id OR away_team_id is in the affected set) AND `season_id = '2026-spring-hs'` are updated to `season_id = '2025-summer-usssa'`.
- [ ] **AC-7**: All `plays` rows linked to the corrected games have season_id updated to `'2025-summer-usssa'` (run AFTER games UPDATE).
- [ ] **AC-8**: All `player_season_batting` and `player_season_pitching` rows WHERE team_id in the affected set AND `season_id = '2026-spring-hs'` are updated.
- [ ] **AC-9**: All `team_rosters` rows WHERE team_id in the affected set AND `season_id = '2026-spring-hs'` are updated.
- [ ] **AC-10**: All `spray_charts` rows WHERE team_id in the affected set AND `season_id = '2026-spring-hs'` are updated. (Note: `spray_charts.season_id` is nullable -- the WHERE clause must account for this.)
- [ ] **AC-11**: `scouting_runs.season_id` is NOT updated. Per TN-1/TN-6, it is a file-discovery column and must retain the crawl directory value so `src/pipeline/trigger.py` and `src/reports/generator.py` can locate files on disk.
- [ ] **AC-12**: Re-running the migration does not fail or produce duplicate rows. All UPDATE and INSERT statements are idempotent.
- [ ] **AC-13**: A test verifies the migration corrects season_id values (can be a Python test that applies the migration to an in-memory DB with test data and asserts the corrections).

## Technical Approach
A SQL migration file per Technical Notes TN-6. The migration must prepend `PRAGMA foreign_keys=ON;` because `executescript()` resets connection state.

**Execution order**: (1) PRAGMA, (2) program creation + team assignment, (3) season row creation, (4) affected-team CTE + UPDATE statements.

For the affected team discovery (AC-5): use a SQL CTE that collects `{126} UNION SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126`. Each UPDATE references this CTE.

The `plays` UPDATE runs AFTER the `games` UPDATE and joins through `games` to find affected rows (plays link via `game_id` → `games`).

Per TN-6, the composite PK concern for `team_rosters` (`team_id, player_id, season_id`) is safe because `2025-summer-usssa` is a new season_id with no existing rows.

Per TN-6, the composite PK concern for `team_rosters` (`team_id, player_id, season_id`) is safe because `2025-summer-usssa` is a new season_id with no existing rows.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `migrations/011_fix_season_id_rebels_14u.sql` -- new migration file
- `tests/test_migration_011.py` -- new test file (AC-13)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This migration is specific to the known Rebels 14U case and its opponents. If additional teams are discovered with wrong season_id values, a follow-up migration can be added.
- The migration does NOT need to handle the general case of deriving season_id from team metadata for all teams -- that's what the loader changes (stories 02/03) are for.
- Per the migrations convention, UPDATE-only migrations are safe without DDL-level idempotency because `apply_migrations.py` tracks applied migrations in `_migrations` and runs each exactly once. The old-value WHERE clauses are defense-in-depth.
