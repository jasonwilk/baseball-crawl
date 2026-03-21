# E-143: Admin Management Overhaul -- Operational Usability

## Status
`READY`

## Overview
Make the admin UI a complete operational interface so the system operator can manage teams, programs, opponents, crawls, and users entirely through the browser -- eliminating CLI commands and manual SQL for routine operations. This is the bridge from "developer tool" to "usable system" and directly enables pre-game scouting workflows.

## Background & Context
The admin UI currently handles team listing/add/edit/toggle-active, user CRUD with team assignments, and opponent discovery with manual mapping. But several critical operator workflows still require CLI access or manual SQL:
- No way to delete stale/mis-entered teams from the UI
- Crawls can only be triggered via `bb data crawl` / `bb data scout` CLI commands
- Programs can only be created via seed SQL (table exists, no admin form)
- Opponent manual mapping flow exists but the "Connect" action is hard to discover for unresolved opponents
- No role-based access control -- admin access is gated by `ADMIN_EMAIL` env var, not database-driven roles

The user asked "what am I missing?" Expert consultation surfaced two additional must-haves:
- **Crawl status/freshness visibility** (baseball-coach): A crawl trigger is useless without feedback. "Last synced" timestamps and success/failure indicators are essential for operator confidence and coaching trust.
- **Programs management tab** (ux-designer): Programs are a first-class entity that need their own admin surface, not just a dropdown option.

**Expert consultations completed**:
- **baseball-coach**: Opponent mapping (#1 coaching value) + crawl freshness (#2) are the two features that make the system usable for pre-game scouting. Coaches are data consumers, not operators -- role system maps cleanly to this.
- **api-scout**: Crawl pipeline is callable as Python API. `scouting_runs` table already tracks scouting status. Public endpoints work for opponent preview. Reverse bridge restricted to followed teams -- not needed for this workflow.
- **software-engineer**: Opponent mapping flow is substantially implemented (6 routes exist). Crawl UI needs per-team pipeline scoping + async execution. Delete should be scoped to zero-data teams (12 FK references, no CASCADE).
- **data-engineer**: Feature 4 schema is purpose-built (no migration). Feature 5 needs `ALTER TABLE users ADD COLUMN role`. Feature 1: soft-delete already works via `is_active`; hard delete only safe for zero-data teams.
- **ux-designer**: Most features extend existing pages. Programs sub-tab is the main structural addition. Opponent mapping needs discoverability polish. Crawl sync/async pattern is the biggest UX question.

## Goals
- Operator can manage the full team lifecycle (add, edit, deactivate, delete) from the browser
- Operator can trigger data refresh for any team from the browser and see whether it succeeded
- Operator can create programs without manual SQL
- Unresolved opponents are clearly surfaced with an obvious path to manual mapping
- Role-based access allows multiple admins and prevents non-admin users from modifying system configuration

## Non-Goals
- Scheduled/automated crawl orchestration (future -- see IDEA-012)
- Real-time crawl progress streaming (fire-and-forget with status tracking is sufficient)
- Granular per-route permissions beyond admin/user binary
- Season management UI
- Program edit/delete (defer unless needed)
- Coaching dashboard changes -- this epic is admin/operator UI only
- Opponent auto-resolution improvements (14% null `progenitor_team_id` is an API limitation)
- Magic link / invite flow for new users (separate epic)
- Opponent mapping status on schedule view (capture as idea)

## Success Criteria
- All 5 user-requested features are functional in the admin UI
- Zero CLI commands required for routine operations (team CRUD, crawl trigger, program creation, user roles)
- Crawl status is visible on the teams list (last synced timestamp, success/failure indicator)
- Unresolved opponents are visually distinct and the Connect flow is obvious
- Non-admin users cannot access team/program/user management routes

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-143-01 | Program list and create admin page | TODO | None | SE |
| E-143-02 | User role schema migration | TODO | None | DE |
| E-143-05 | Per-team crawl pipeline scoping | TODO | None | DE |
| E-143-06a | Crawl jobs schema migration | TODO | E-143-02 | DE |
| E-143-02b | Admin role enforcement in UI | TODO | E-143-01, E-143-02 | SE |
| E-143-04 | Opponent mapping UX polish | TODO | E-143-01 | SE |
| E-143-03 | Delete deactivated zero-data teams | TODO | E-143-02b, E-143-06a | SE |
| E-143-06 | Crawl trigger UI with status display | TODO | E-143-03, E-143-05, E-143-06a | SE |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### TN-1: Admin Route File and Shared Templates
All admin routes live in `src/api/routes/admin.py`. Stories 01, 02b, 03, and 06 add or modify routes in this file. All admin templates live under `src/api/templates/admin/`. Since dispatch executes serially with staging boundary (`git add -A` after each story), each story sees the prior story's committed state. Stories should add new route functions rather than restructuring existing ones.

**Shared file note**: Stories 01, 02b, 03, and 06 all modify `src/api/routes/admin.py`. Stories 03 and 06 both modify `src/api/templates/admin/teams.html`. Implementers should expect prior stories may have already added routes or template markup to these files.

### TN-1a: Admin Sub-Nav Is Inline, Not a Partial
The admin sub-navigation is NOT a shared Jinja2 partial. It exists as inline markup duplicated in 7 separate templates: `src/api/templates/admin/teams.html`, `src/api/templates/admin/users.html`, `src/api/templates/admin/opponents.html`, `src/api/templates/admin/edit_user.html`, `src/api/templates/admin/edit_team.html`, `src/api/templates/admin/confirm_team.html`, and `src/api/templates/admin/opponent_connect.html`. Any story adding a new nav tab (e.g., "Programs" in E-143-01) must update all 7 existing templates plus any new templates it creates.

### TN-2: Crawl Execution Pattern
Two distinct pipelines exist:
- **Member team crawl**: Full pipeline via `src/pipeline/crawl.py:run()` (roster → schedule → opponents → stats → game-stats). Currently iterates all active member teams -- E-143-05 adds per-team scoping. **Important**: `crawl.run()` defaults to `source="yaml"` (YAML config). Per-team DB-backed filtering requires `source="db"` so the pipeline reads teams from the database where `TeamEntry.internal_id` is available for filtering. E-143-05 adds `team_ids` as a parameter that works with `source="db"`. E-143-06 must call `crawl.run(source="db", team_ids=[team_id])`.
- **Opponent scouting crawl**: `ScoutingCrawler.scout_team(public_id)` -- already per-team.

The UI "Sync" button should invoke the appropriate pipeline based on `membership_type` (`member` → full crawl, `tracked` → scouting crawl). **Both crawl and load steps are required** -- `bb data sync` = crawl + load, so a UI sync must also run both. For member teams: `crawl.run(source="db", team_ids=[id])` then `load.run(source="db", team_ids=[id])`. For tracked teams: the scouting pipeline's combined crawl+load flow. Without the load step, crawled data stays in `data/raw/` and dashboards remain stale. Note: `load.run()` currently has a `source` parameter but no `team_ids` -- E-143-05 must add per-team scoping to both `crawl.run()` and `load.run()`.

Use FastAPI `BackgroundTasks` for async execution -- the route returns immediately with a flash message and the sync runs in the background.

Auth freshness: call token refresh at the start of each crawl invocation to avoid mid-run expiration (access token has ~61-minute lifetime).

The sync route must also update `teams.last_synced` to the current timestamp on job completion, so the existing edit_team page continues to show a meaningful last-synced value. `crawl_jobs` provides detailed history; `teams.last_synced` provides the quick summary view. Both are kept in sync.

### TN-3: Team Deletion Safety
12 tables reference `teams(id)` with no `ON DELETE CASCADE`. Hard deletion requires explicit cleanup.

**Approach**: Allow hard delete ONLY when `is_active = 0` AND no dependent rows exist in data tables (`games`, `player_game_batting`, `player_game_pitching`, `player_season_batting`, `player_season_pitching`, `scouting_runs`, `spray_charts`). If data exists, redirect to `/admin/teams` with an error flash explaining the team has associated data and cannot be deleted. Use the redirect + query-parameter flash pattern consistent with the rest of the admin UI (not a 400 response body).

When deletion proceeds (zero data), clean up junction/access rows in a transaction: `team_opponents` (both FK columns), `team_rosters`, `opponent_links` (both FK columns), `user_team_access`, `coaching_assignments`, `crawl_jobs` (added by E-143-06a), then the `teams` row.

### TN-4: User Role Model
Add `role TEXT NOT NULL DEFAULT 'user'` to `users` table via migration. Two values: `admin`, `user`. Application-layer validation (SQLite cannot add CHECK constraints via ALTER TABLE to existing tables).

Transition from `ADMIN_EMAIL` env var:
1. Migration adds column; all existing users get `role = 'user'` via DEFAULT.
2. `_require_admin()` updated to accept EITHER `ADMIN_EMAIL` match OR `role = 'admin'`. The current dev-mode fallback (grant admin when `ADMIN_EMAIL` is unset) is removed. Bootstrap path: set `ADMIN_EMAIL` to your email, or use SQL to set `role='admin'` on your user row.
3. Operator manually promotes themselves: `UPDATE users SET role='admin' WHERE email='...'` or via a seed mechanism.
4. `ADMIN_EMAIL` remains as a bootstrap fallback (not retired).

Protected routes: all `/admin/teams/*`, `/admin/programs/*`, `/admin/users/*` management actions. All routes under `/admin/opponents/*` remain admin-only -- no change needed; this is the current behavior. E-143-04's opponent mapping polish does not change opponent access control. Read-only dashboard routes remain accessible to all authenticated users.

### TN-5: Opponent Mapping Existing State
The full opponent discovery + manual mapping flow is already implemented:
- `POST /admin/teams/{id}/discover-opponents` -- triggers GC opponent discovery
- `GET /admin/opponents` -- lists all opponent links with status
- `GET /admin/opponents/{link_id}/connect` -- URL paste form
- `GET /admin/opponents/{link_id}/connect/confirm` -- preview before save
- `POST /admin/opponents/{link_id}/connect` -- saves manual mapping
- `POST /admin/opponents/{link_id}/disconnect` -- removes mapping

The `opponent_links` table tracks: `root_team_id`, `resolved_team_id`, `public_id`, `resolution_method` (auto/manual/boxscore), `is_hidden`. Auto-resolution handles ~86% of opponents via `progenitor_team_id`. The ~14% unlinked have `public_id IS NULL` and need the manual Connect flow.

**Important**: `save_manual_opponent_link()` sets `public_id` and `resolution_method='manual'` but deliberately keeps `resolved_team_id = NULL` (the reverse bridge returns 403 for opponent teams). Therefore, the correct "unresolved" predicate is `public_id IS NULL` (not `resolved_team_id IS NULL`). The existing DB code in `src/api/db.py` already uses `public_id IS NULL` for the "scoresheet only" filter.

E-143-04 improves discoverability of this existing flow -- no new backend routes needed.

### TN-6: Programs Table Schema
The `programs` table has: `program_id TEXT PRIMARY KEY`, `name TEXT NOT NULL`, `program_type TEXT NOT NULL` (CHECK: hs/usssa/legion), `org_name TEXT`, `created_at TIMESTAMP`. The `program_id` is an operator-chosen slug (e.g., `lsb-hs`). No migration needed -- the table exists.

### TN-7: Sub-Navigation Extension
Current admin sub-nav: **Users | Teams | Opponents**. E-143-01 adds a **Programs** tab: **Users | Teams | Programs | Opponents**. Per TN-1a, this requires updating all 7 existing templates that contain the inline nav markup (`teams.html`, `users.html`, `opponents.html`, `edit_user.html`, `edit_team.html`, `confirm_team.html`, `opponent_connect.html`), plus any new templates created by E-143-01.

## Open Questions
- None -- all expert consultations resolved.

## History
- 2026-03-21: Created (DRAFT). Expert consultations: baseball-coach, api-scout, software-engineer, data-engineer, ux-designer.
- 2026-03-21: Spec review complete. 7 codex rounds + 1 code-reviewer round. All findings resolved. Marked READY.
