# E-100-01: Schema Rewrite — Complete DDL with Full Stat Coverage

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, the database schema will be a single `001_initial_schema.sql` containing the complete DDL: programs, INTEGER PK teams, team_opponents junction, all non-computed stats from the GameChanger glossary on per-game and season stat tables, provenance columns, spray_charts with pitcher_id, and all auth tables. Old migrations are archived. The seed/reset script produces a valid seeded database against the new schema. Tests verify schema correctness.

## Context
Fresh-start rewrite — user authorized dropping all data. The existing `migrations/001_initial_schema.sql` on main is the OLD E-003 schema (250 lines, TEXT PK teams, is_owned, level). This story writes the complete new DDL from scratch, archives old migrations, updates the seed/reset script, and writes schema verification tests. All tables (data + auth) are in a single migration file — one file, one source of truth.

## Acceptance Criteria

### Migration Structure
- [ ] **AC-1**: Old migration files (001-008) are archived in `.project/archive/migrations-pre-E100/`. The `migrations/` directory contains only `001_initial_schema.sql` plus `__init__.py` and `apply_migrations.py`.
- [ ] **AC-2**: A fresh `python migrations/apply_migrations.py` on a new `data/app.db` creates all tables successfully. All FK constraints are valid.
- [ ] **AC-3**: Migration comment block documents the INTEGER PK convention per the epic Technical Notes.
- [ ] **AC-4**: All auth tables (users, sessions, magic_link_tokens, user_credentials, coaching_assignments) are included in `001_initial_schema.sql`. Single migration file is the complete schema.

### Core Tables
- [ ] **AC-5**: `programs` table exists with columns: `program_id TEXT PK`, `name TEXT NOT NULL`, `program_type TEXT NOT NULL CHECK(program_type IN ('hs', 'usssa', 'legion'))`, `org_name TEXT`, `created_at`. One seed row: `('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear')`.
- [ ] **AC-6**: `teams` table has `id INTEGER PK AUTOINCREMENT`, `name`, `program_id FK`, `membership_type CHECK(... IN ('member', 'tracked'))`, `classification` (with CHECK for known values + NULL), `public_id TEXT UNIQUE`, `gc_uuid TEXT UNIQUE`, `source`, `is_active`, `last_synced`, `created_at`. No `is_owned` column. No `level` column. No `team_id TEXT` column.
- [ ] **AC-7**: `team_opponents` table exists with INTEGER FKs to `teams(id)`, UNIQUE constraint, and `CHECK(our_team_id != opponent_team_id)`.
- [ ] **AC-8**: `seasons` table has `program_id TEXT FK -> programs` (nullable).
- [ ] **AC-9**: `opponent_links` table exists with INTEGER FK references (`our_team_id INTEGER FK -> teams(id)`, `resolved_team_id INTEGER FK -> teams(id)`).
- [ ] **AC-10**: `scouting_runs` table exists with INTEGER FK to `teams(id)`.

### Enriched Columns
- [ ] **AC-11**: `players` table has `bats TEXT`, `throws TEXT`, and `gc_athlete_profile_id TEXT` columns.
- [ ] **AC-12**: `games` table has `game_stream_id TEXT` column.
- [ ] **AC-13**: `player_game_batting` has all columns listed in the epic Technical Notes "Complete Stat Column Reference — player_game_batting" section. This includes structural columns (batting_order, positions_played, is_primary, stat_completeness), main stats (ab, r, h, rbi, bb, so), extra stats (singles, doubles, triples, hr, tb, hbp, shf, sb, cs, e), and enrichment stats (pitches, strikes, pa).
- [ ] **AC-14**: `player_game_pitching` has all columns listed in the epic Technical Notes "Complete Stat Column Reference — player_game_pitching" section. This includes structural columns (decision, stat_completeness), main stats (ip_outs, h, r, er, bb, so), extra stats (wp, hbp, hr), and enrichment stats (pitches, strikes, bf).
- [ ] **AC-15**: `player_season_batting` has all columns listed in the epic Technical Notes "Complete Stat Column Reference — player_season_batting" section. This includes structural columns (stat_completeness, games_tracked), all standard batting stats (26+), advanced batting stats (countable only), and nullable split columns (home/away, vs_lhp/vs_rhp).
- [ ] **AC-16**: `player_season_pitching` has all columns listed in the epic Technical Notes "Complete Stat Column Reference — player_season_pitching" section. This includes structural columns (stat_completeness, games_tracked), all standard pitching stats (35+), advanced pitching stats (countable only), and nullable split columns (home/away, vs_lhb/vs_rhb).
- [ ] **AC-17**: `spray_charts` table exists with columns: `id INTEGER PK`, `game_id TEXT FK`, `player_id TEXT FK`, `team_id INTEGER FK`, `pitcher_id TEXT FK -> players(player_id)` (nullable), `chart_type TEXT CHECK(IN ('offensive', 'defensive'))`, `play_type TEXT`, `play_result TEXT`, `x REAL`, `y REAL`, `fielder_position TEXT`, `error INTEGER DEFAULT 0`.

### Remaining Tables
- [ ] **AC-18**: All other tables (team_rosters, auth tables, coaching_assignments) exist with correct schema. All FK references to teams use `teams(id)` (INTEGER).

### Seed and Tests
- [ ] **AC-19**: `scripts/reset_dev_db.py` (and `bb db reset`) works with the new schema — seed data uses `membership_type` and `classification`, not `is_owned` or `level`. Seed data for INTEGER PK teams uses subquery references (not hardcoded IDs).
- [ ] **AC-20**: Tests verify: (a) migrations apply on fresh DB, (b) programs table seeded correctly, (c) teams table has correct columns and constraints, (d) team_opponents constraints work, (e) all stat table columns exist per the Complete Stat Column Reference, (f) stat_completeness column exists on all four stat tables with correct CHECK constraints, (g) games_tracked column exists on both season stat tables, (h) spray_charts table exists with pitcher_id FK, (i) reset script produces a valid seeded database, (j) auth tables exist with correct schema.

## Technical Approach
Write the complete DDL from scratch in `migrations/001_initial_schema.sql`. Archive existing migration files (001-008) to `.project/archive/migrations-pre-E100/`. The DDL must include all tables (data + auth) in FK dependency order. Use `docs/gamechanger-stat-glossary.md` as the authoritative source for stat column names — cross-reference the "Complete Stat Column Reference" section in the epic Technical Notes for the exact stat list per table. Update `src/db/reset.py` seed data for the new schema. Write schema verification tests. The migration must follow conventions in `/.claude/rules/migrations.md`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-100-02, E-100-03, E-100-04, E-100-05, E-100-06

## Files to Create or Modify
- `migrations/001_initial_schema.sql` (REWRITE — replace old E-003 schema with complete new DDL)
- `migrations/003_auth.sql` (ARCHIVE — content folded into 001)
- `migrations/004_coaching_assignments.sql` (ARCHIVE — content folded into 001)
- `migrations/005_teams_public_id.sql` (ARCHIVE — content folded into 001)
- `migrations/006_opponent_links.sql` (ARCHIVE — content folded into 001)
- `migrations/007_scouting_uuid.sql` (ARCHIVE — content folded into 001)
- `migrations/008_scouting_timestamps.sql` (ARCHIVE — content folded into 001)
- `src/db/reset.py` (MODIFY — update seed data)
- `tests/test_seed.py` (MODIFY — update for new schema)
- Tests for schema verification (CREATE)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-100-02**: Clean `teams` table with INTEGER PK (`id`), `membership_type` and `classification` columns. `programs` table with seed data. All child tables have `team_id INTEGER REFERENCES teams(id)`. All stat tables have provenance columns. Auth tables included. db.py and auth.py can now be migrated to INTEGER references.
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
- All new stat and enrichment columns are nullable — populated by follow-up epics, not E-100.
- The `_migrations` table conflict is moot — user is deleting `data/app.db`.
- Computed stats (AVG, OBP, OPS, SLG, ERA, WHIP, BABIP, FIP, etc.) are NOT stored as columns — they are derived at query time.
- Fielding, catcher, and pitch type stats are deferred to follow-up tables (purely additive, no FK deps).
