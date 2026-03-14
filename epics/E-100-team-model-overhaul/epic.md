# E-100: Team Model Overhaul — Team-First Data Model

## Status
`READY`

## Overview
Fresh-start rebuild of the team data model into a team-first architecture. Drops all existing data (user confirmed), rewrites the schema from scratch with INTEGER PK for teams, programs as organizational metadata, membership_type replacing is_owned, and complete stat coverage per the GameChanger stat glossary. All application code (db.py, auth.py, pipeline, admin, dashboard) is updated in one coordinated epic with no backward-compatibility concerns.

## Background & Context
The current model hardcodes Lincoln Standing Bear assumptions: `is_owned` distinguishes "our" teams from opponents, `level` stores HS-specific values, and the admin UI splits teams into "Lincoln Program" and "Tracked Opponents." The user's GameChanger account spans 19 teams across travel ball (8U-14U), high school, and Legion — none fit the current model.

**Fresh-start authorization (2026-03-14):** User authorized dropping all data and rebuilding from scratch. No migration compatibility, no xfail patterns, no intermediate broken states. Each story writes clean code and clean tests against the new schema. Data will be re-seeded after the epic completes.

**Standing design principle (2026-03-14):** Store every stat that GameChanger tracks. The schema includes columns for every non-computed stat in `docs/gamechanger-stat-glossary.md`. If it's in the glossary, it belongs in the schema. Computed stats (rates, percentages, ratios like AVG, OBP, ERA, WHIP) are derived at query time and do not need columns.

**Expert consultation completed (three rounds):**
- **Data Engineer (round 1)**: Clean rewrite of migration 001, programs table, team_opponents junction, INTEGER AUTOINCREMENT PK for teams only.
- **Data Engineer (round 2)**: Enriched schema with coach's requirements: game_stream_id on games, batting_order/pitches/strikes on player_game_batting, bats/throws on players, nullable split columns on season stats tables, spray_charts table. Nullable columns confirmed over split_type discriminator rows.
- **Data Engineer (round 3)**: Cross-referenced full glossary against schema. All non-computed batting stats (26+), pitching stats (35+) mapped to columns. Provenance model: `stat_completeness` + `games_tracked` on season tables, `data_source` on per-game tables. Fielding/catcher/pitch type tables deferred (purely additive, no FK deps).
- **Software Engineer**: Mapped full code surface (~30 db.py functions, auth.py, 2 route files, 2 loaders, crawl config, 12 templates, ~12 test files). Confirmed Wave 3 parallelism is safe. Identified 10 simplifications from dropping backward compat: `_generate_opponent_team_id`, `_resolve_team_ids`, placeholder rename pattern all deleted.
- **Baseball Coach**: Defined three circles of data (my team, opponents, longitudinal). Confirmed structural decisions in E-100, data population in follow-ups. Key schema additions: game lines for both teams (game_stream_id enables public boxscore access), player handedness (bats/throws), batting order per game, nullable split columns. Spray charts, streak flags, and L/R data population are follow-up epics.
- **UX Designer**: Two-phase add-team flow, flat team list, division optgroup dropdown, membership auto-detect. Coach interview surfaced scouting report, rate stats, proactive flags — all scoped out.

## Goals
- Clean schema with INTEGER PK for teams, eliminating the gc_uuid/public_id identity duality
- Complete stat columns per GC glossary: all non-computed batting stats on per-game and season tables, all non-computed pitching stats on per-game and season tables, spray_charts table with pitcher_id — structure only, populated by follow-up epics
- Stat provenance tracking: `stat_completeness` on all four stat tables, `games_tracked` on season tables
- Member/tracked distinction is system-computed (via GC bridge auto-detect), not operator-declared
- Programs as lightweight organizational metadata for grouping teams (not a navigation frame)
- Two-phase add-team flow resolves team from GC URL, auto-detects membership, pre-populates division
- Admin team list displays all teams in a flat list with program/division columns and membership badges
- All application code updated to use INTEGER team references and membership_type
- Clean tests throughout — no xfail markers, no fixture-splitting between stories

## Non-Goals
- **Populating enriched columns**: New stat columns, game_stream_id, batting_order, bats/throws, spray_charts, and split columns are added to the DDL but NOT populated by any E-100 story. Population is follow-up epic scope.
- **Multi-credential per program**: Different GC accounts for HS vs USSSA programs. Deferred.
- **Bulk import from /me/teams**: Batch onboarding of all 19 teams. Deferred.
- **Program CRUD admin page**: No admin UI for creating/editing programs in E-100. Programs are created via direct SQL or a follow-up epic. The add-team confirm page has a dropdown for existing programs only.
- **Opponent page redesign**: `/admin/opponents` stays as-is. Only opponent counts with filtered links added to team list.
- **Dashboard program-awareness**: No program-based navigation or filtering. INTEGER PK compatibility only.
- **Scouting report redesign**: Rate stats, proactive flags, PDF export — all follow-up epics.
- **Populating gc_athlete_profile_id**: Column added to DDL; E-104 populates it.
- **Program-first dashboard navigation**: Explicitly rejected. Team-and-season is the primary lens.
- **L/R split data population**: Schema supports nullable split columns; population is follow-up.
- **Spray chart ingestion pipeline**: spray_charts table created; crawler + loader are follow-up.
- **Fielding, catcher, and pitch type tables**: Deferred. Purely additive (no FK references from other tables), doesn't block anything. Add in a follow-up when a loader exists.
- **Travel ball tier/division column**: Not needed at this time. Follow-up if needed (USSSA, AA, AAA, Majors).
- **Stat blending logic**: Loaders that merge API season stats with boxscore-derived stats are follow-up scope. E-100 creates the provenance columns; population strategy is deferred.

## Success Criteria
- `programs` table exists with at least one seeded program (Lincoln Standing Bear HS)
- `teams` table has INTEGER AUTOINCREMENT PK (`id`), plus `program_id`, `membership_type`, `classification`, `gc_uuid`, and `public_id` columns
- `team_opponents` junction table exists
- All non-computed stats from `docs/gamechanger-stat-glossary.md` have corresponding columns in the appropriate stat tables (see Complete Stat Column Reference in Technical Notes)
- Provenance columns exist: `stat_completeness` on all four stat tables, `games_tracked` on season stat tables
- `spray_charts` table exists with `pitcher_id` FK
- All crawlers, loaders, CLI commands, db.py, auth.py, admin routes, and dashboard routes use INTEGER team PKs and `membership_type` instead of `is_owned`
- Admin team list displays all teams in a flat list with program, division, and membership columns
- Adding a team via GC URL auto-detects membership and pre-populates program/division on a confirm page
- All tests pass — no xfail markers, no fixture hacks

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-100-01 | Schema rewrite: complete DDL with full stat coverage | TODO | None | - |
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

**Approach:**
1. Archive all existing migration files (001-008) to `.project/archive/migrations-pre-E100/`
2. Write a single new `migrations/001_initial_schema.sql` — complete DDL for all tables (data + auth) in dependency order
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

### Complete Stat Column Reference

Derived from `docs/gamechanger-stat-glossary.md`. Only non-computed stats (countable values) are stored as columns. Computed stats (rates, percentages, ratios) are derived at query time. Column naming is DE's decision; stat names below are from the glossary.

#### player_game_batting
Per-player per-game batting stats from boxscore endpoint.

**Structural columns:** game_id FK, player_id FK, team_id INTEGER FK, batting_order INTEGER, positions_played TEXT, is_primary INTEGER (1=starter, 0=sub), stat_completeness TEXT CHECK('full','supplemented','boxscore_only')

**Main stats (always present in boxscore):** ab, r, h, rbi, bb, so

**Extra stats (sparse in boxscore — non-zero only):** singles (1B), doubles (2B), triples (3B), hr, tb, hbp, shf (sac flies), sb, cs, e (errors)

**Enrichment (from boxscore extras):** pitches (#P — pitches seen), strikes (TS — strikes seen)

**Also available:** pa (plate appearances — can be computed from ab+bb+hbp+shf+hbp but also tracked directly)

#### player_game_pitching
Per-player per-game pitching stats from boxscore endpoint.

**Structural columns:** game_id FK, player_id FK, team_id INTEGER FK, decision TEXT CHECK('W','L','SV') nullable, stat_completeness TEXT CHECK('full','supplemented','boxscore_only')

**Main stats (always present in boxscore):** ip_outs INTEGER (total outs — 3 outs = 1 IP), h, r, er, bb, so

**Extra stats (sparse in boxscore — non-zero only):** wp, hbp, hr

**Enrichment (from boxscore extras):** pitches (#P — pitch count), strikes (TS — total strikes), bf (batters faced)

#### player_season_batting
Per-player per-season aggregate batting stats. All non-computed batting stats from the glossary.

**Structural columns:** player_id FK, team_id INTEGER FK, season_id FK, stat_completeness TEXT CHECK('full','supplemented','boxscore_only'), games_tracked INTEGER

**Standard batting (26+ stats):** gp, pa, ab, h, singles (1B), doubles (2B), triples (3B), hr, rbi, r, bb, so, sol (K looking), hbp, shb (sac bunts), shf (sac flies), roe, fc, sb, cs, pik, tb, xbh, lob, two_out_rbi (2OUTRBI), gidp, gitp, ci

**Advanced batting (countable only):** qab, hard (HHB count), lnd (line drives), flb (fly balls), gb (ground balls), ps (pitches seen), two_s_plus_3 (2S+3), six_plus (6+)

**Split columns (nullable — populated by follow-up epics):**
- Home/away for key stats: home_ab, home_h, home_hr, home_bb, home_so, away_ab, away_h, away_hr, away_bb, away_so
- vs LHP/RHP for key stats: vs_lhp_ab, vs_lhp_h, vs_lhp_hr, vs_lhp_bb, vs_lhp_so, vs_rhp_ab, vs_rhp_h, vs_rhp_hr, vs_rhp_bb, vs_rhp_so

#### player_season_pitching
Per-player per-season aggregate pitching stats. All non-computed pitching stats from the glossary.

**Structural columns:** player_id FK, team_id INTEGER FK, season_id FK, stat_completeness TEXT CHECK('full','supplemented','boxscore_only'), games_tracked INTEGER

**Standard pitching (35+ stats):** gp, gs, ip_outs, bf, pitches (#P), total_strikes (TS), total_balls (TB), w, l, sv, svo, bs, h, r, er, bb, so, sol (K looking), hbp, lob, bk, pik, cs, sb, wp, hr

**Advanced pitching (countable only):** lbfpn (LBFP#), lt_3 (<3 pitch batters), loo (leadoff outs), first_2_out (1ST2OUT), inn_123 (123INN), lt_13 (<13 pitch innings), zero_bb_inn (0BBINN), bbs (walks that score), lobb (leadoff walks), lobbs (leadoff walks that score), sm (swings and misses), sw (total swings), go (ground outs), ao (air outs), weak (WHB count), hard (HHB count), lnd (line drives), fb (fly balls), gb (ground balls)

**Split columns (nullable — populated by follow-up epics):**
- Home/away for key stats: home_ip_outs, home_h, home_er, home_bb, home_so, away_ip_outs, away_h, away_er, away_bb, away_so
- vs LHB/RHB for key stats: vs_lhb_ab, vs_lhb_h, vs_lhb_hr, vs_lhb_bb, vs_lhb_so, vs_rhb_ab, vs_rhb_h, vs_rhb_hr, vs_rhb_bb, vs_rhb_so

#### spray_charts
Ball-in-play direction data. Table created in E-100; ingestion pipeline is a follow-up.

**Columns:** id INTEGER PK, game_id TEXT FK, player_id TEXT FK, team_id INTEGER FK, pitcher_id TEXT FK -> players(player_id) nullable, chart_type TEXT CHECK('offensive','defensive'), play_type TEXT, play_result TEXT, x REAL, y REAL, fielder_position TEXT, error INTEGER DEFAULT 0

### Provenance Model

**All four stat tables** get `stat_completeness`:
- `stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only'` — CHECK('full', 'supplemented', 'boxscore_only')
  - `full`: all columns populated from the team's own API endpoint (season-stats or per-game)
  - `supplemented`: API data canonical, supplemented with boxscore data for gaps
  - `boxscore_only`: all stats derived from boxscore aggregation (typical for opponents)

**Season stat tables** (`player_season_batting`, `player_season_pitching`) additionally get:
- `games_tracked INTEGER` — number of games used to derive the stats (for boxscore_only/supplemented rows)

E-100 creates these columns with defaults. Loaders that set non-default values are follow-up scope.

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
- 2026-03-14: Final refinement round. Standing design principle established: "store every stat GC tracks." Third DE consultation: glossary cross-reference, provenance model (three-state stat_completeness + games_tracked), fielding/catcher/pitch type tables deferred. Schema expanded to include all non-computed batting (26+) and pitching (35+) stats from glossary. spray_charts gains pitcher_id. Program CRUD deferred. DDL rescoped as full creation work (prior DE branch not on main). Three unassigned test files (test_seed.py, test_coaching_assignments.py, test_passkey.py) assigned to stories. Auth tables folded into single 001_initial_schema.sql.
