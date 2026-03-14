# E-100: Team Model Overhaul — Team-First Data Model

## Status
`READY`

## Overview
Fresh-start rebuild of the team data model into a team-first architecture. Drops all existing data (user confirmed), rewrites the schema from scratch with INTEGER PK for teams, programs as organizational metadata, membership_type replacing is_owned, and enriched stat columns from coaching consultation. All application code (db.py, auth.py, pipeline, admin, dashboard) is updated in one coordinated epic with no backward-compatibility concerns.

## Background & Context
The current model hardcodes Lincoln Standing Bear assumptions: `is_owned` distinguishes "our" teams from opponents, `level` stores HS-specific values, and the admin UI splits teams into "Lincoln Program" and "Tracked Opponents." The user's GameChanger account spans 19 teams across travel ball (8U-14U), high school, and Legion — none fit the current model.

**Fresh-start authorization (2026-03-14):** User authorized dropping all data and rebuilding from scratch. No migration compatibility, no xfail patterns, no intermediate broken states. Each story writes clean code and clean tests against the new schema. Data will be re-seeded after the epic completes.

**Expert consultation completed (two rounds):**
- **Data Engineer (round 1)**: Clean rewrite of migration 001, programs table, team_opponents junction, INTEGER AUTOINCREMENT PK for teams only. 17-table refined schema delivered.
- **Data Engineer (round 2)**: Enriched schema with coach's requirements: game_stream_id on games, batting_order/pitches/strikes on player_game_batting, bats/throws on players, nullable split columns on season stats tables, spray_charts table. Nullable columns confirmed over split_type discriminator rows.
- **Software Engineer**: Mapped full code surface (~30 db.py functions, auth.py, 2 route files, 2 loaders, crawl config, 12 templates, ~12 test files). Confirmed Wave 3 parallelism is safe. Identified 10 simplifications from dropping backward compat: `_generate_opponent_team_id`, `_resolve_team_ids`, placeholder rename pattern all deleted.
- **Baseball Coach**: Defined three circles of data (my team, opponents, longitudinal). Confirmed structural decisions in E-100, data population in follow-ups. Key schema additions: game lines for both teams (game_stream_id enables public boxscore access), player handedness (bats/throws), batting order per game, nullable split columns. Spray charts, streak flags, and L/R data population are follow-up epics.
- **UX Designer**: Two-phase add-team flow, flat team list, division optgroup dropdown, membership auto-detect. Coach interview surfaced scouting report, rate stats, proactive flags — all scoped out.

## Goals
- Clean schema with INTEGER PK for teams, eliminating the gc_uuid/public_id identity duality
- Enriched stat columns (game_stream_id, batting_order, pitches/strikes, bats/throws, nullable split columns, spray_charts table) — structure only, populated by follow-up epics
- Member/tracked distinction is system-computed (via GC bridge auto-detect), not operator-declared
- Programs as lightweight organizational metadata for grouping teams (not a navigation frame)
- Two-phase add-team flow resolves team from GC URL, auto-detects membership, pre-populates division
- Admin team list displays all teams in a flat list with program/division columns and membership badges
- All application code updated to use INTEGER team references and membership_type
- Clean tests throughout — no xfail markers, no fixture-splitting between stories

## Non-Goals
- **Populating enriched columns**: game_stream_id, batting_order, pitches/strikes, bats/throws, spray_charts, and split columns are added to the DDL but NOT populated by any E-100 story. Population is follow-up epic scope.
- **Multi-credential per program**: Different GC accounts for HS vs USSSA programs. Deferred.
- **Bulk import from /me/teams**: Batch onboarding of all 19 teams. Deferred.
- **Opponent page redesign**: `/admin/opponents` stays as-is. Only opponent counts with filtered links added to team list.
- **Dashboard program-awareness**: No program-based navigation or filtering. INTEGER PK compatibility only.
- **Scouting report redesign**: Rate stats, proactive flags, PDF export — all follow-up epics.
- **Populating gc_athlete_profile_id**: Column added to DDL; E-104 populates it.
- **Program-first dashboard navigation**: Explicitly rejected. Team-and-season is the primary lens.
- **L/R split data population**: Schema supports nullable split columns; population is follow-up.
- **Spray chart ingestion pipeline**: spray_charts table created; crawler + loader are follow-up.

## Success Criteria
- `programs` table exists with at least one seeded program (Lincoln Standing Bear HS)
- `teams` table has INTEGER AUTOINCREMENT PK (`id`), plus `program_id`, `membership_type`, `classification`, `gc_uuid`, and `public_id` columns
- `team_opponents` junction table exists
- Enriched columns exist: `game_stream_id` on games, `batting_order`/`pitches`/`strikes` on player_game_batting, `bats`/`throws` on players, nullable split columns on season stats, `spray_charts` table
- All crawlers, loaders, CLI commands, db.py, auth.py, admin routes, and dashboard routes use INTEGER team PKs and `membership_type` instead of `is_owned`
- Admin team list displays all teams in a flat list with program, division, and membership columns
- Adding a team via GC URL auto-detects membership and pre-populates program/division on a confirm page
- All tests pass — no xfail markers, no fixture hacks

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-100-01 | Schema rewrite: enriched 17-table DDL | TODO | None | - |
| E-100-02 | Data layer: db.py + auth.py INTEGER PK | TODO | E-100-01 | - |
| E-100-03 | Pipeline: membership_type + TeamRef + INTEGER PK | TODO | E-100-02 | - |
| E-100-04 | Admin UI: team list + add-team flow + INTEGER URLs | TODO | E-100-02 | - |
| E-100-05 | Dashboard: INTEGER PK migration | TODO | E-100-02 | - |
| E-100-06 | Context-layer updates | TODO | E-100-03, E-100-04, E-100-05 | - |

## Dispatch Team
- data-engineer (E-100-01)
- software-engineer (E-100-02, E-100-03, E-100-04, E-100-05)
- claude-architect (E-100-06)

## Technical Notes

### Schema Strategy: Fresh-Start Rewrite

User authorized dropping all data ("drop everything, rebuild from scratch"). This is NOT a migration — it is a complete schema replacement.

**Current state (as of 2026-03-14):** The migration DDL (`migrations/001_initial_schema.sql`, 563 lines) and migration archival (`.project/archive/migrations-pre-E100/`) already exist on disk from a prior DE session. The DDL includes all coach/DE enrichments. E-100-01 validates the existing DDL, updates the seed/reset script, and writes schema verification tests.

**Approach:**
1. ~~Archive all existing migration files (001-008)~~ *(already done)*
2. ~~Write a single new `migrations/001_initial_schema.sql`~~ *(already done — 17 tables in dependency order)*
3. User deletes `data/app.db` and runs `python migrations/apply_migrations.py` to get the new schema
4. Update seed data script for new schema
5. Write schema verification tests

**Why INTEGER PK for teams (not TEXT):** The TEXT PK convention (`team_id = gc_uuid for member, public_id for tracked`) creates an identity problem — the same column means different things depending on membership type, and a tracked team that later becomes a member would need its PK changed (breaking all FK references). INTEGER AUTOINCREMENT PK separates internal DB identity from external GC identifiers. `gc_uuid` and `public_id` live in their own UNIQUE columns for external lookups. INTEGER PK applies to `teams` only — programs, seasons, and players keep TEXT PKs.

### Schema Design

**New table: `programs`**
```
programs
  program_id    TEXT PK        -- slug: 'lsb-hs', 'lsb-legion', 'nebraska-quakes-14u'
  name          TEXT NOT NULL   -- 'Lincoln Standing Bear HS'
  program_type  TEXT NOT NULL   -- CHECK(program_type IN ('hs', 'usssa', 'legion'))
  org_name      TEXT            -- optional umbrella org name
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
```

**Rewritten: `teams`** (INTEGER PK, no `is_owned`, no `level`)
```
teams
  id              INTEGER PK AUTOINCREMENT  -- internal DB identity
  name            TEXT NOT NULL
  program_id      TEXT FK -> programs(program_id)  -- nullable (opponents have no program)
  membership_type TEXT NOT NULL   -- CHECK(membership_type IN ('member', 'tracked'))
  classification  TEXT            -- CHECK(known values) or NULL
  public_id       TEXT UNIQUE     -- GC slug for public endpoint access
  gc_uuid         TEXT UNIQUE     -- GC UUID for authenticated endpoint access
  source          TEXT NOT NULL DEFAULT 'gamechanger'
  is_active       INTEGER NOT NULL DEFAULT 1
  last_synced     TEXT
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
```

**New table: `team_opponents`**
```
team_opponents
  id                INTEGER PK AUTOINCREMENT
  our_team_id       INTEGER NOT NULL FK -> teams(id)
  opponent_team_id  INTEGER NOT NULL FK -> teams(id)
  first_seen_year   INTEGER
  UNIQUE(our_team_id, opponent_team_id)
  CHECK(our_team_id != opponent_team_id)
```

**Updated: `seasons`** (program_id FK added)
```
seasons
  season_id     TEXT PK
  name          TEXT NOT NULL
  season_type   TEXT NOT NULL
  year          INTEGER NOT NULL
  program_id    TEXT FK -> programs(program_id)  -- nullable
  start_date    TEXT
  end_date      TEXT
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
```

**Updated: `players`** (bats, throws, gc_athlete_profile_id added)
```
players
  ... (existing columns)
  bats                   TEXT     -- 'L', 'R', 'S' (switch)
  throws                 TEXT     -- 'L', 'R'
  gc_athlete_profile_id  TEXT     -- cross-team identity anchor (deliberately secondary)
```

**Updated: `games`** (game_stream_id added)
```
games
  ... (existing columns)
  game_stream_id  TEXT     -- GC game stream ID for public endpoint access to game details
```

**Updated: `player_game_batting`** (batting_order, pitches, strikes added)
```
player_game_batting
  ... (existing columns)
  batting_order  INTEGER   -- lineup position (1-9)
  pitches        INTEGER   -- total pitches seen
  strikes        INTEGER   -- total strikes seen
```

**Updated: `player_season_batting` and `player_season_pitching`** (nullable split columns)
Split data uses nullable columns (not discriminator rows). Columns for vs_lhp/vs_rhp/home/away variants of key stats. Only 'overall' rows are populated in E-100; split columns remain NULL until follow-up epics populate them. DE's refined DDL specifies the exact column set.

**New table: `spray_charts`**
Ball-in-play direction data (x/y coordinates, play type, result, fielder). Table created in E-100; ingestion pipeline is a follow-up epic (aligns with IDEA-009).

**Kept: `opponent_links`** (FK references updated to INTEGER)

**Classification CHECK constraint:**
```sql
CHECK(classification IS NULL OR classification IN (
    'varsity', 'jv', 'freshman', 'reserve',
    '8U', '9U', '10U', '11U', '12U', '13U', '14U',
    'legion'
))
```

**Convention documented in migration comment:**
```
-- teams.id is an internal INTEGER AUTOINCREMENT primary key.
-- External GC identifiers live in their own columns:
--   gc_uuid:   the team's UUID from authenticated GC API (UNIQUE)
--   public_id: the team's slug from public GC URLs (UNIQUE)
-- All FK references to teams use teams(id), never gc_uuid or public_id.
-- Lookups by external identifier use the gc_uuid/public_id UNIQUE indexes.
```

**Seed data in migration:** One program row: `('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear')`

### Opponent Model Split
- `opponent_links` stays as-is: GC registry resolution queue. FK references updated to INTEGER.
- `team_opponents` is the new clean domain relationship: "team X plays opponent Y." INTEGER FKs to `teams(id)`.
- Future: when opponent_resolver completes a resolution, it should also INSERT into team_opponents.

### Season Scoping on team_opponents
The junction table intentionally lacks a `season_id` column — it models a permanent "we have faced this team" relationship. The coaching question "who do we play THIS season?" is answered via the games table (which has `season_id`), not `team_opponents`.

### Membership Auto-Detect (Bridge-Based)
The existing reverse bridge (`GET /teams/public/{slug}/id`) returns 403 for non-member teams. Flow:
1. User pastes GC URL -> parse to public_id
2. Try reverse bridge -> success = member (store returned UUID as gc_uuid), 403 = tracked
3. Show confirm page with auto-detected membership_type
4. On confirm: INSERT into teams (INTEGER PK auto-assigned)

### Admin UI Design (Team-First)
- **Two-phase add-team**: Phase 1 = URL input (simplified form). Phase 2 = confirm page showing resolved team info, auto-detected membership, optional program dropdown and division dropdown.
- **Team list**: Flat table of all teams. Columns: team name, program, division, membership badge, active/inactive, opponent count, edit link.
- **Division dropdown**: Single optgroup dropdown (HS group: varsity/JV/freshman/reserve; USSSA group: 8U-14U; Other: legion).
- **Edit page**: Program assignment, division, name override, active toggle. Membership is display-only.
- **Program creation on confirm page**: Deferred. Dropdown for existing programs only.

### Fresh Start Philosophy
"Each season is a fresh start. Same kid, new team, new opportunities." Current season is the primary lens. Historical data is available but subordinate — never leading, always supporting.

### Season Slug Parameterization
`_derive_season_id()` in `scouting.py` hardcodes `"-spring-hs"` suffix. Add a `season_suffix` parameter threaded through `ScoutingCrawler.__init__()`. Default to `"spring-hs"`.

### CrawlConfig Changes
- `owned_teams` -> `member_teams` (field rename)
- `TeamEntry.is_owned` -> removed (membership_type lives on DB row)
- `load_config_from_db()`: `WHERE is_active=1 AND membership_type='member'`

### TeamRef Pattern (SE Design)
```
@dataclass
class TeamRef:
    id: int           # internal DB PK (teams.id)
    gc_uuid: str      # GC UUID for authenticated API calls
    public_id: str | None  # GC slug for public API calls
```

Pipeline code uses `.id` for all DB operations and `.gc_uuid` / `.public_id` for API calls.

### db.py + auth.py INTEGER PK Migration
~30 query functions with TEXT `team_id` parameters. All must change to INTEGER. `get_permitted_teams()` returns `list[int]`. Stub-INSERT patterns use `membership_type='tracked'` and auto-assigned INTEGER PK.

### Dashboard INTEGER PK Impact
Dashboard routes use `?team_id=` query params. With INTEGER PKs, these must parse as int and compare against `list[int]` from `get_permitted_teams()`. 12 template files reference `team_id` in links and selectors.

### Fresh-Start Simplifications
With no backward compatibility:
- `_generate_opponent_team_id()` deleted entirely (no TEXT slug generation)
- `_resolve_team_ids()` replaced by new two-phase resolution function
- No placeholder rename pattern
- Test fixtures write fresh INTEGER PK data
- No xfail/skip markers between stories
- Each story's tests pass independently against the new schema

### Wave Plan
- **Wave 1**: E-100-01 (schema — foundation, no deps)
- **Wave 2**: E-100-02 (db.py + auth.py — foundational data layer, depends on 01)
- **Wave 3**: E-100-03 + E-100-04 + E-100-05 (parallel — pipeline / admin / dashboard, no file overlap)
- **Wave 4**: E-100-06 (context-layer, depends on all implementation stories)

## Open Questions
- None remaining. All design decisions resolved through expert consultation.

## History
- 2026-03-13: Created. Expert consultation with DE, SE, UXD completed.
- 2026-03-13: User confirmed no data preservation needed. INTEGER PK for teams confirmed. E-102 absorbed. Vision pivot to team-first model.
- 2026-03-13: Multi-expert review completed. 4 MUST FIX, 5 SHOULD FIX, 4 ADVISORY items applied.
- 2026-03-14: Fresh-start redesign. User authorized dropping all data and rebuilding. Second-round expert consultation: coach defined three circles of data and 7 schema gaps; DE delivered enriched 17-table DDL (game_stream_id, batting_order, pitches/strikes, bats/throws, nullable split columns, spray_charts); SE confirmed 10 simplifications from dropping backward compat. Coach confirmed nullable columns over split_type discriminator. Epic restructured from 7 stories / 5 waves to 6 stories / 4 waves (merged admin UI + add-team flow into one story, eliminated 04->06 serialization, removed xfail pattern).
