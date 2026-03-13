# E-100-01: Schema Rewrite — Programs, Teams, Team Opponents, Seasons

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, the database schema will be cleanly rewritten with programs as a first-class entity, teams using `membership_type` and `classification` (no `is_owned`, no `level`), a `team_opponents` junction table for opponent relationships, and `program_id` FK on seasons. Old migration files (001-008) will be archived. The user deletes `data/app.db` and runs migrations to get the new schema. The seed/reset script will be updated for the new schema.

## Context
This is the foundation story for the team model overhaul. Every subsequent story depends on these schema changes. The user confirmed no data worth preserving ("We can start over if we need to"), enabling a clean rewrite of migration 001 instead of additive ALTER TABLE changes. This eliminates deprecated columns, avoids migration complexity, and produces a clean schema from the start. All 8 existing migration files are archived, and a new 001 expresses the complete target schema. Auth tables (003) and coaching_assignments (004) are folded into the single migration or kept as separate files with updated FKs.

## Acceptance Criteria
- [ ] **AC-1**: Old migration files (001, 003, 004, 005, 006, 007, 008) are archived to `.project/archive/migrations-pre-E100/`. The `migrations/` directory contains only the new schema file(s) plus `__init__.py` and `apply_migrations.py`.
- [ ] **AC-2**: A fresh `python migrations/apply_migrations.py` on a new `data/app.db` creates all tables successfully with the new schema. All FK constraints are valid.
- [ ] **AC-3**: `programs` table exists with columns: `program_id TEXT PK`, `name TEXT NOT NULL`, `program_type TEXT NOT NULL CHECK(program_type IN ('hs', 'usssa', 'legion'))`, `org_name TEXT`, `created_at`. One seed row: `('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear')`.
- [ ] **AC-4**: `teams` table has columns: `id INTEGER PK AUTOINCREMENT`, `name TEXT NOT NULL`, `program_id TEXT FK → programs`, `membership_type TEXT NOT NULL CHECK('member', 'tracked')`, `classification TEXT` (with CHECK constraint for known values + NULL), `public_id TEXT UNIQUE`, `gc_uuid TEXT UNIQUE`, `source TEXT NOT NULL DEFAULT 'gamechanger'`, `is_active INTEGER NOT NULL DEFAULT 1`, `last_synced TEXT`, `created_at`. No `is_owned` column. No `level` column. No `team_id TEXT` column.
- [ ] **AC-5**: `team_opponents` table exists with columns: `id INTEGER PK AUTOINCREMENT`, `our_team_id INTEGER NOT NULL FK → teams(id)`, `opponent_team_id INTEGER NOT NULL FK → teams(id)`, `first_seen_year INTEGER`, `UNIQUE(our_team_id, opponent_team_id)`.
- [ ] **AC-6**: `seasons` table has `program_id TEXT FK → programs` column (nullable) in addition to existing columns.
- [ ] **AC-7**: `opponent_links` table exists with FK references updated to INTEGER (`our_team_id INTEGER FK → teams(id)`, `resolved_team_id INTEGER FK → teams(id)`).
- [ ] **AC-8**: `scouting_runs` table exists with the same structure as migration 007 (unchanged).
- [ ] **AC-9**: All other tables (players, team_rosters, games, player_game_batting, player_game_pitching, player_season_batting, player_season_pitching, auth tables, coaching_assignments) exist with correct schema. FK references to teams use `teams(id)` (INTEGER).
- [ ] **AC-10**: Migration comment block documents the INTEGER PK convention: `teams.id` is internal identity; `gc_uuid` and `public_id` are external lookup columns with UNIQUE indexes.
- [ ] **AC-11**: `scripts/reset_dev_db.py` (and `bb db reset`) works correctly with the new schema — seed data uses `membership_type` and `classification`, not `is_owned` or `level`.
- [ ] **AC-12**: Tests verify: (a) migrations apply on fresh DB, (b) programs table seeded correctly, (c) teams table has correct columns and constraints, (d) team_opponents table exists with correct constraints, (e) reset script produces a valid seeded database.

## Technical Approach
Refer to the epic's Technical Notes "Schema Strategy: Clean Rewrite of Migration 001" and "Schema Design" sections for the full specification. The migration must follow the conventions in `/.claude/rules/migrations.md`. Use `CREATE TABLE IF NOT EXISTS` for all tables, `CREATE INDEX IF NOT EXISTS` for all indexes. The existing `apply_migrations.py` runner tracks migrations by filename in a `_migrations` table — ensure the new filename(s) are distinct from archived ones.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-100-02, E-100-03, E-100-04, E-100-05, E-100-06, E-100-07

## Files to Create or Modify
- `migrations/001_initial_schema.sql` (REWRITE — or new numbered file if cleaner)
- `migrations/003_auth.sql` (KEEP or FOLD INTO 001 — agent's discretion)
- `migrations/004_coaching_assignments.sql` (KEEP or FOLD INTO 001 — agent's discretion)
- `.project/archive/migrations-pre-E100/` (CREATE — archive directory for old migrations)
- `src/db/reset.py` or `scripts/reset_dev_db.py` (MODIFY — update seed data)
- Tests for schema verification (CREATE — test file location at agent's discretion)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-100-02**: Clean `teams` table with INTEGER PK (`id`), `membership_type` and `classification` columns (no `is_owned`, no `level`). `programs` table with seed data. All child tables have `team_id INTEGER REFERENCES teams(id)`. db.py and auth.py can now be migrated to INTEGER references.
- **Produces for E-100-03**: Schema foundation for pipeline INTEGER PK migration (TeamRef pattern, stub-INSERT refactor).
- **Produces for E-100-04**: `programs` table with seed data. `classification` column. `membership_type` column. INTEGER PK for admin URL parameters.
- **Produces for E-100-05**: INTEGER PK schema for dashboard query migration.
- **Produces for E-100-06**: `team_opponents` junction table (INTEGER FKs). Add-team flow can insert team rows with INTEGER PK auto-assigned.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `classification` CHECK constraint enumerates known values: `'varsity', 'jv', 'freshman', 'reserve', '8U', '9U', '10U', '11U', '12U', '13U', '14U'` plus NULL. NULL is allowed because opponents and some legion teams have no classification.
- INTEGER AUTOINCREMENT PK applies to `teams` only. Programs, seasons, and players keep TEXT PKs (they have stable, non-dual external identifiers). All FK references to teams across all tables use `teams(id)` (INTEGER), not `gc_uuid` or `public_id`.
- Whether to write one monolithic 001 or keep 001 + 003 + 004 as separate files is at the agent's discretion. A single file is cleaner for a fresh start; separate files preserve the logical grouping (data model vs auth vs coaching assignments). Either approach must produce the same final schema.
- The `_migrations` table in existing databases tracks old filenames. Since the user is deleting `data/app.db`, there is no conflict. But if the agent keeps filenames identical to archived ones (e.g., reusing `001_initial_schema.sql`), document this clearly.
