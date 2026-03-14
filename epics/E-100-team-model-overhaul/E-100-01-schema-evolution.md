# E-100-01: Schema Rewrite — Enriched 17-Table DDL

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, the database schema will be a clean 17-table DDL with programs, INTEGER PK teams, team_opponents junction, enriched stat columns, and updated FKs throughout. The seed/reset script produces a valid seeded database against the new schema. Tests verify schema correctness.

**Note:** The migration DDL (`migrations/001_initial_schema.sql`) and migration archival (`.project/archive/migrations-pre-E100/`) already exist on disk from a prior DE session. This story validates the existing DDL against the ACs below, updates the seed/reset script, and writes schema verification tests. If the existing DDL satisfies all ACs, no DDL changes are needed.

## Context
Fresh-start rewrite — user authorized dropping all data. DE delivered the refined 17-table DDL (already committed to `migrations/001_initial_schema.sql`, 563 lines). Old migrations are already archived to `.project/archive/migrations-pre-E100/`. Remaining work: seed/reset script update and schema verification tests.

## Acceptance Criteria

### Migration Structure
- [ ] **AC-1**: Old migration files are archived in `.project/archive/migrations-pre-E100/`. The `migrations/` directory contains only `001_initial_schema.sql` plus `__init__.py` and `apply_migrations.py`. *(Verify — already done on disk.)*
- [ ] **AC-2**: A fresh `python migrations/apply_migrations.py` on a new `data/app.db` creates all tables successfully. All FK constraints are valid.
- [ ] **AC-3**: Migration comment block documents the INTEGER PK convention per the epic Technical Notes. *(Verify — already in the DDL header.)*

### Core Tables
- [ ] **AC-4**: `programs` table exists with columns: `program_id TEXT PK`, `name TEXT NOT NULL`, `program_type TEXT NOT NULL CHECK(program_type IN ('hs', 'usssa', 'legion'))`, `org_name TEXT`, `created_at`. One seed row: `('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear')`.
- [ ] **AC-5**: `teams` table has `id INTEGER PK AUTOINCREMENT`, `name`, `program_id FK`, `membership_type CHECK(... IN ('member', 'tracked'))`, `classification` (with CHECK for known values + NULL), `public_id TEXT UNIQUE`, `gc_uuid TEXT UNIQUE`, `source`, `is_active`, `last_synced`, `created_at`. No `is_owned` column. No `level` column. No `team_id TEXT` column.
- [ ] **AC-6**: `team_opponents` table exists with INTEGER FKs to `teams(id)`, UNIQUE constraint, and `CHECK(our_team_id != opponent_team_id)`.
- [ ] **AC-7**: `seasons` table has `program_id TEXT FK -> programs` (nullable).
- [ ] **AC-8**: `opponent_links` table exists with INTEGER FK references (`our_team_id INTEGER FK -> teams(id)`, `resolved_team_id INTEGER FK -> teams(id)`).
- [ ] **AC-9**: `scouting_runs` table exists with INTEGER FK to `teams(id)`.

### Enriched Columns
- [ ] **AC-10**: `players` table has `bats TEXT`, `throws TEXT`, and `gc_athlete_profile_id TEXT` columns.
- [ ] **AC-11**: `games` table has `game_stream_id TEXT` column.
- [ ] **AC-12**: `player_game_batting` table has `batting_order INTEGER`, `pitches INTEGER`, `strikes INTEGER` columns (plus `hbp`, `pa`, `positions_played` from DE's enrichment).
- [ ] **AC-13**: `player_season_batting` has nullable split columns: `home_ab`, `home_h`, `home_hr`, `home_bb`, `home_so`, `away_ab`, `away_h`, `away_hr`, `away_bb`, `away_so`, `vs_lhp_ab`, `vs_lhp_h`, `vs_lhp_hr`, `vs_lhp_bb`, `vs_lhp_so`, `vs_rhp_ab`, `vs_rhp_h`, `vs_rhp_hr`, `vs_rhp_bb`, `vs_rhp_so`. Plus `hbp` and `pa` overall columns.
- [ ] **AC-14**: `player_season_pitching` has nullable split columns: `home_ip_outs`, `home_h`, `home_er`, `home_bb`, `home_so`, `away_ip_outs`, `away_h`, `away_er`, `away_bb`, `away_so`, `vs_lhb_ab`, `vs_lhb_h`, `vs_lhb_hr`, `vs_lhb_bb`, `vs_lhb_so`, `vs_rhb_ab`, `vs_rhb_h`, `vs_rhb_hr`, `vs_rhb_bb`, `vs_rhb_so`. Plus `bf` overall column. *(Note: pitching uses vs_lhb/vs_rhb — vs left/right-handed BATTER, not pitcher.)*
- [ ] **AC-15**: `spray_charts` table exists with columns: `id INTEGER PK`, `game_id TEXT FK`, `player_id TEXT FK`, `team_id INTEGER FK`, `chart_type TEXT CHECK(IN ('offensive', 'defensive'))`, `play_type TEXT`, `play_result TEXT`, `x REAL`, `y REAL`, `fielder_position TEXT`, `error INTEGER DEFAULT 0`.

### Remaining Tables
- [ ] **AC-16**: All other tables (team_rosters, player_game_pitching, auth tables, coaching_assignments) exist with correct schema. All FK references to teams use `teams(id)` (INTEGER).

### Seed and Tests
- [ ] **AC-17**: `scripts/reset_dev_db.py` (and `bb db reset`) works with the new schema — seed data uses `membership_type` and `classification`, not `is_owned` or `level`. Seed data for INTEGER PK teams uses subquery references (not hardcoded IDs).
- [ ] **AC-18**: Tests verify: (a) migrations apply on fresh DB, (b) programs table seeded correctly, (c) teams table has correct columns and constraints, (d) team_opponents constraints work, (e) enriched columns exist on all enriched tables, (f) spray_charts table exists with correct columns, (g) reset script produces a valid seeded database.

## Technical Approach
The migration DDL already exists at `migrations/001_initial_schema.sql`. Validate it against the ACs above. If any AC is not satisfied, update the DDL. Update `src/db/reset.py` seed data for the new schema. Write schema verification tests. The migration must follow conventions in `/.claude/rules/migrations.md`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-100-02, E-100-03, E-100-04, E-100-05, E-100-06

## Files to Create or Modify
- `migrations/001_initial_schema.sql` (VERIFY existing — modify only if ACs not met)
- `src/db/reset.py` (MODIFY — update seed data)
- Tests for schema verification (CREATE)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-100-02**: Clean `teams` table with INTEGER PK (`id`), `membership_type` and `classification` columns. `programs` table with seed data. All child tables have `team_id INTEGER REFERENCES teams(id)`. db.py and auth.py can now be migrated to INTEGER references.
- **Produces for E-100-03**: Schema foundation for pipeline INTEGER PK migration (TeamRef pattern, stub-INSERT refactor).
- **Produces for E-100-04**: `programs` table, `classification` column, `membership_type` column, `team_opponents` junction, INTEGER PK for admin URL parameters.
- **Produces for E-100-05**: INTEGER PK schema for dashboard query migration.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- Classification CHECK uses mixed case intentionally (`'jv'` lowercase, `'14U'` uppercase) — documented in migration comment.
- INTEGER AUTOINCREMENT PK applies to `teams` only. Programs, seasons, and players keep TEXT PKs.
- Enriched columns are all nullable — populated by follow-up epics, not E-100.
- The `_migrations` table conflict is moot — user is deleting `data/app.db`.
