# E-100: Team Model Overhaul — Team-First Data Model

## Status
`READY`

## Overview
Clean up the LSB-centric team data model into a team-first architecture where one coach works with one team in one season. Replaces the owned/opponent binary with system-detected member/tracked membership, adds INTEGER PK for stable team identity, introduces a unified "Division" classification, and streamlines the admin team management UI with a two-phase add-team flow. Programs exist as lightweight organizational metadata for grouping teams — not as navigation frames or primary entities.

## Background & Context
The current model hardcodes Lincoln Standing Bear assumptions: `is_owned` distinguishes "our" teams from opponents, `level` stores HS-specific values (varsity/JV/freshman/reserve), and the admin UI splits teams into "Lincoln Program" and "Tracked Opponents." The user's GameChanger account actually spans 19 teams across travel ball (8U-14U, 2019-2025), high school (6 teams, 2026 spring), and Legion — none of which fit cleanly into the current model.

The user intends to make this system available to youth (USSSA) coaches as well, requiring the platform to support multiple program types with different classification schemes: HS uses levels (varsity, JV, freshman, reserve), USSSA uses age groups (8U-14U), and Legion stands alone.

**Expert consultation completed:**
- **Data Engineer**: Recommended clean rewrite of migration 001 (user confirmed no data worth preserving), programs table, split opponent model (team_opponents junction + keep opponent_links as resolution queue), single classification column with CHECK constraint. Confirmed INTEGER AUTOINCREMENT PK for `teams` table only (not programs/seasons/players) — eliminates the gc_uuid/public_id duality that prevents stable team identity.
- **Software Engineer**: Confirmed INTEGER PK is architecturally correct. Designed `TeamRef` dataclass pattern (`id: int, gc_uuid: str, public_id: str | None`) to separate DB identity from external API identity. Confirmed bridge-based auto-detect membership (reverse bridge 403s on non-member teams). Identified season slug hardcoding in one function. Recommended deferring multi-credential to a later epic. Codex spec review revealed INTEGER PK blast radius extends to db.py (~30 query functions), auth.py, dashboard.py, and 12 templates — all must migrate together with the schema (no valid intermediate state).
- **UX Designer**: Designed two-phase add-team flow (URL input → confirm page with auto-detected membership), program-grouped accordion team list, "Division" as universal label, optgroup division dropdown, sub-page for inline program creation. Coach interview surfaced scouting report, rate stats, proactive flags, and PDF export requirements — all scoped out of E-100 into separate future epics.

## Goals
- Clean schema with INTEGER PK for teams, eliminating the gc_uuid/public_id identity duality
- Member/tracked distinction is system-computed (via GC bridge auto-detect), not operator-declared
- Programs as lightweight organizational metadata for grouping teams (not a navigation frame)
- Two-phase add-team flow resolves team from GC URL, auto-detects membership, pre-populates division
- Admin team list displays all teams with program/division columns and membership badges
- Opponents remain inside teams via a clean junction table (team_opponents)
- Clean schema rewrite (user confirmed no data preservation needed) — no deprecated columns
- Season model gains optional program_id FK

## Non-Goals
- **Multi-credential per program**: Different GC accounts for HS vs USSSA programs. Deferred to a later epic. This epic assumes all member teams are accessible from a single GC account. (SE confirmed: no technical debt if credential_profile is NOT stored on programs.)
- **Bulk import from /me/teams**: Fetching all 19 teams at once for batch onboarding. UXD reserved a UI slot ("Import from GC" button placeholder) but the flow is not built in this epic.
- **Opponent page redesign**: The `/admin/opponents` page stays as-is. Only per-team opponent counts with filtered links are added to the team list.
- **Dashboard program-awareness**: Dashboard navigation by program is a separate epic. E-100 updates dashboard code for INTEGER PK compatibility but does not add program-based navigation or filtering.
- **Scouting report redesign**: Coach interview surfaced rate stats, proactive flags, PDF export, schedule-as-scouting-entry, and matchup suggestions. All captured as vision signals and scoped for separate future epics.
- **Program-first dashboard navigation**: Explicitly rejected. The user confirmed "separate front doors is NOT worth it." Team-and-season is the primary lens; programs are organizational metadata, not navigation frames.

## Success Criteria
- `programs` table exists with at least one seeded program (Lincoln Standing Bear HS)
- `teams` table has INTEGER AUTOINCREMENT PK (`id`), plus `program_id`, `membership_type`, `classification`, `gc_uuid`, and `public_id` columns
- `team_opponents` junction table exists
- All existing crawlers, loaders, CLI commands, db.py, auth.py, admin routes, and dashboard routes use INTEGER team PKs and `membership_type` instead of `is_owned`
- Admin team list displays all teams in a flat list with program, division, and membership columns
- Adding a team via GC URL auto-detects membership and pre-populates program/division on a confirm page
- All existing tests pass; new tests cover the migration, model changes, and admin flows

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-100-01 | Schema rewrite: programs, teams, team_opponents, seasons | TODO | None | - |
| E-100-02 | Data layer INTEGER PK: db.py + auth.py | TODO | E-100-01 | - |
| E-100-03 | Pipeline: is_owned → membership_type + TeamRef + INTEGER PK | TODO | E-100-02 | - |
| E-100-04 | Admin UI: team list, division, INTEGER URLs | TODO | E-100-02 | - |
| E-100-05 | Dashboard routes + templates INTEGER PK | TODO | E-100-02 | - |
| E-100-06 | Admin UI: two-phase add-team flow with auto-detect | TODO | E-100-03, E-100-04 | - |
| E-100-07 | Context-layer updates | TODO | E-100-01 through E-100-06 | - |

## Dispatch Team
- data-engineer (E-100-01)
- software-engineer (E-100-02, E-100-03, E-100-04, E-100-05, E-100-06)
- claude-architect (E-100-07)

## Technical Notes

### Schema Strategy: Clean Rewrite of Migration 001

User confirmed no data worth preserving ("We can start over if we need to"). This enables a clean rewrite rather than additive ALTER TABLE changes.

**Approach:**
1. Archive all 8 existing migration files (001-008) to `.project/archive/migrations-pre-E100/`
2. Write a single new `migrations/001_initial_schema.sql` expressing the complete target schema — all 20 tables (including auth and coaching_assignments) in one file, in dependency order
3. User deletes `data/app.db` and runs `python migrations/apply_migrations.py` to get the new schema
4. Update `scripts/reset_dev_db.py` seed data for new schema

DE has drafted the complete DDL (20 tables, indexes, seed data). The implementing agent should request the INTEGER PK version from DE's consultation output as the reference specification.

**Why INTEGER PK for teams (not TEXT):** The TEXT PK convention (`team_id = gc_uuid for member, public_id for tracked`) creates an identity problem — the same column means different things depending on membership type, and a tracked team that later becomes a member would need its PK changed (breaking all FK references). INTEGER AUTOINCREMENT PK separates internal DB identity from external GC identifiers. `gc_uuid` and `public_id` live in their own UNIQUE columns for external lookups. INTEGER PK applies to `teams` only — programs, seasons, and players keep TEXT PKs (they have stable, non-dual external identifiers). The full INTEGER PK code migration is included in E-100 (stories 02-05) because there is no valid intermediate state — all code must be updated to use INTEGER team references before any tests can pass against the new schema.

### Schema Design

**New table: `programs`**
```
programs
  program_id    TEXT PK        -- slug: 'lsb-hs', 'lsb-legion', 'nebraska-quakes-14u'
  name          TEXT NOT NULL   -- 'Lincoln Standing Bear HS'
  program_type  TEXT NOT NULL   -- CHECK('hs', 'usssa', 'legion')
  org_name      TEXT            -- optional umbrella org name
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
```

**Rewritten: `teams`** (replaces old teams table — no `is_owned`, no `level`, INTEGER PK)
```
teams
  id              INTEGER PK AUTOINCREMENT  -- internal DB identity
  name            TEXT NOT NULL
  program_id      TEXT FK → programs(program_id)  -- nullable (opponents have no program)
  membership_type TEXT NOT NULL   -- CHECK('member', 'tracked')
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
  our_team_id       INTEGER NOT NULL FK → teams(id)
  opponent_team_id  INTEGER NOT NULL FK → teams(id)
  first_seen_year   INTEGER
  UNIQUE(our_team_id, opponent_team_id)
```

**Updated: `seasons`** (program_id FK added)
```
seasons
  season_id     TEXT PK
  name          TEXT NOT NULL
  season_type   TEXT NOT NULL
  year          INTEGER NOT NULL
  program_id    TEXT FK → programs(program_id)  -- nullable
  start_date    TEXT
  end_date      TEXT
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
```

**Updated: `players`** (gc_athlete_profile_id added)
```
players
  ... (existing columns unchanged)
  gc_athlete_profile_id  TEXT     -- cross-team identity anchor; prior-season data
                                  -- available via this link but not the primary query path.
                                  -- No UNIQUE constraint, no index (deliberately secondary).
```

**Kept: `opponent_links`** (FK references updated: `our_team_id INTEGER`, `resolved_team_id INTEGER`)

**Classification CHECK constraint:**
```sql
CHECK(classification IS NULL OR classification IN (
    'varsity', 'jv', 'freshman', 'reserve',
    '8U', '9U', '10U', '11U', '12U', '13U', '14U'
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
- `opponent_links` stays as-is: GC registry resolution queue (root_team_id → resolved_team_id). FK references updated to INTEGER (`our_team_id INTEGER`, `resolved_team_id INTEGER`).
- `team_opponents` is the new clean domain relationship: "team X plays opponent Y." References resolved canonical team entities via `teams(id)` INTEGER FK, not GC registry keys.
- Seeding: resolved opponent_links rows seed team_opponents during migration. Unresolved opponents stay in opponent_links pending resolution.
- Future: when opponent_resolver completes a resolution, it should also INSERT into team_opponents.

### Membership Auto-Detect (Bridge-Based)
The existing reverse bridge (`GET /teams/public/{slug}/id`) returns 403 for non-member teams. This IS the auto-detect mechanism — no `/me/teams` call needed. Flow:
1. User pastes GC URL → parse to public_id
2. Try reverse bridge → success = member (store returned UUID as gc_uuid), 403 = tracked
3. Show confirm page with auto-detected membership_type
4. On confirm: INSERT into teams (INTEGER PK auto-assigned, gc_uuid and public_id stored in their respective columns)

### Admin UI Design (Team-First, Revised)
- **Two-phase add-team**: Phase 1 = URL input (current page, simplified). Phase 2 = confirm page (`/admin/teams/confirm`) showing resolved team info, auto-detected membership, optional program dropdown and division dropdown.
- **Team list**: Flat table of all teams (no accordion, no program-grouped sections). Columns: team name, program (if assigned), division (classification), membership badge (● Member green / ○ Tracked gray), active/inactive, opponent count, edit link. Sortable by any column. Programs are metadata, not the visual hierarchy.
- **Division dropdown**: Single optgroup dropdown (HS group: varsity/JV/freshman/reserve; USSSA group: 8U-14U; Other: legion). No cascading dependency on program type.
- **Edit page**: Program assignment (dropdown of existing programs), division, name override, active toggle all editable. Membership is display-only (system-computed). Program creation deferred — programs are created via the edit page dropdown or a future admin programs page, not via a dedicated sub-page flow.
- **Program creation on confirm page**: Deferred. The confirm page offers a program dropdown for existing programs only. If no program matches, the team is created without a program — the operator can assign one later via the edit page.

### Fresh Start Philosophy
The user's guiding principle: "Each season is a fresh start. Same kid, new team, new opportunities." Current season is the primary lens. Historical data (prior seasons, cross-team player identity) is available but subordinate — never leading, always supporting. The schema enables cross-team queries (via `gc_athlete_profile_id`, `program_id` FK on seasons) but the UX will never lead with historical data. Current season stats are the main story; prior seasons are footnotes, available when asked for, not pushed. This shapes all future dashboard and scouting work, not just E-100.

### Season Slug Parameterization
`_derive_season_id()` in `scouting.py` hardcodes `"-spring-hs"` suffix. Add a `season_suffix` parameter threaded through `ScoutingCrawler.__init__()`. Default to `"spring-hs"` for backward compatibility. Future: derive suffix from program's season_type.

### CrawlConfig Changes
- `owned_teams` → `member_teams` (field rename)
- `TeamEntry.is_owned` → removed (membership_type lives on DB row, not config entry)
- `load_config_from_db()`: `WHERE is_active=1 AND is_owned=1` → `WHERE is_active=1 AND membership_type='member'`

### TeamRef Pattern (SE Design)
```
@dataclass
class TeamRef:
    id: int           # internal DB PK (teams.id)
    gc_uuid: str      # GC UUID for authenticated API calls
    public_id: str | None  # GC slug for public API calls
```

Pipeline code receives `TeamRef` objects from config/resolution, uses `.id` for all DB operations, and `.gc_uuid` / `.public_id` for API calls. This eliminates the dual-meaning `team_id` that previously served as both DB key and API identifier.

### db.py + auth.py INTEGER PK Migration
`db.py` has ~30 query functions with TEXT `team_id` parameters and SQL JOINs like `JOIN teams t ON t.team_id = x.team_id`. All must change to `JOIN teams t ON t.id = x.team_id` and accept INTEGER parameters. `auth.py` `get_permitted_teams()` returns TEXT team_ids — must return INTEGER IDs. This is the foundational data layer change that stories 03-05 depend on.

### Dashboard INTEGER PK Impact
Dashboard routes use `?team_id=` query params and compare against `permitted_teams` (TEXT list from auth.py). With INTEGER PKs, these must compare integers. 12 template files reference `team_id` in links and selectors. The dashboard does not gain program-awareness in this epic — only INTEGER PK compatibility.

### Wave Plan
- **Wave 1**: E-100-01 (schema rewrite — foundation, no deps)
- **Wave 2**: E-100-02 (db.py + auth.py INTEGER PK — foundational data layer, depends on 01)
- **Wave 3**: E-100-03 + E-100-04 + E-100-05 (parallel — 03 touches pipeline code, 04 touches admin code, 05 touches dashboard code, no file overlap)
- **Wave 4**: E-100-06 (depends on 03 and 04 — adds new add-team flow to admin.py)
- **Wave 5**: E-100-07 (context-layer, depends on all implementation stories)

## Open Questions
- None remaining. All design decisions resolved through expert consultation.

## History
- 2026-03-13: Created. Expert consultation with DE, SE, UXD completed.
- 2026-03-13: User confirmed no data preservation needed — migration strategy changed from additive 009 to clean rewrite of 001. INTEGER PK proposal evaluated and rejected (SE: would double story scope due to game_loader dual-use of team_id). TEXT PKs with documented convention retained.
- 2026-03-13: Coach interview (via UXD) surfaced scouting report, rate stats, proactive flags, PDF export, program-first nav requirements. All scoped OUT of E-100, captured as 8 vision signals in docs/vision-signals.md. E-100 stays focused on team model + admin team management.
- 2026-03-13: DE delivered full clean 001 DDL (20 tables, TEXT PK version).
- 2026-03-13: User directive: "Do not let scope concerns compromise the architecture." Both DE and SE confirmed INTEGER AUTOINCREMENT PK for `teams` table is architecturally correct. SE designed TeamRef dataclass pattern. INTEGER PK applies to teams only (not programs/seasons/players).
- 2026-03-13: Codex spec review of E-102 (pipeline INTEGER PK migration) revealed structural issue: no valid intermediate state between INTEGER PK schema and TEXT-based code. db.py (~30 query functions), auth.py, dashboard.py, and 12 templates all use TEXT team_id. E-102 absorbed into E-100. Epic restructured from 5 to 7 stories. Non-Goals updated (dashboard code changes now in scope for INTEGER PK compatibility). E-102 abandoned.
- 2026-03-13: Vision pivot — reframed from "multi-program platform" to "team-first data model." User confirmed: one coach, one team, one season is the primary frame. Programs are organizational metadata, not navigation frames. "Separate front doors" explicitly rejected. "Fresh start" philosophy: current season is the main story, historical data is available but subordinate. Epic retitled, overview rewritten, Non-Goals updated (program-first nav: deferred → rejected), Admin UI simplified (flat team list replaces accordion, program creation sub-page deferred), E-100-06 softened (program assignment optional on confirm page). `gc_athlete_profile_id` added to players DDL (cross-team identity anchor, deliberately secondary query path).
