# E-042: Admin Interface and Team Management

## Status
`READY`

## Overview
Give admins the ability to add and manage teams through the web interface by pasting GameChanger public URLs, replacing the static `config/teams.yaml` approach. Once a team is added, its schedule reveals opponents that can also be tracked -- all using public (no-auth) API endpoints.

## Background & Context
The current team configuration is a static YAML file (`config/teams.yaml`) that requires manual editing and redeployment. This was acceptable for bootstrapping, but now that the data pipeline (E-002) and schema (E-003) are complete, team onboarding needs to move into the admin UI.

**Key architectural shift**: Instead of requiring authenticated API access to discover teams (via `GET /me/teams`), admins paste a GameChanger public team URL (e.g., `https://web.gc.com/teams/{public_id}/{url_encoded_name}`). The system extracts the `public_id`, fetches the team profile via the no-auth `GET /public/teams/{public_id}` endpoint, and creates the team record. From there, `GET /public/teams/{public_id}/games` reveals opponents, which can be auto-discovered and tracked.

**What already exists:**
- Admin routes at `/admin/users` (E-023) -- CRUD for users + team access grants
- `teams` table with `is_owned`, `is_active`, `source`, `last_synced` columns
- `user_team_access` join table for team-scoped dashboard access
- `coaching_assignments` domain table (migration 004)
- Public API endpoints confirmed: `GET /public/teams/{public_id}` (no auth), `GET /public/teams/{public_id}/games` (no auth)
- Existing crawlers that read from `config/teams.yaml` via `CrawlConfig`

**What changes:**
- Teams table gets a `public_id` column (nullable -- opponents discovered via schedule may not have one initially)
- New admin pages for team CRUD (add via URL, edit, deactivate)
- Opponent auto-discovery from team schedules via public games endpoint
- Crawl orchestration reads team config from the database instead of YAML

**Expert consultation completed:** UX designer (admin UI layout, team list visual hierarchy, URL input flow), data-engineer (migration 005 validation, public_id-as-team_id soundness, opponent model, season derivation), software-engineer (URL parser feasibility, file conflict assessment, sync API call pattern, crawl script integration).

## Goals
- Admin can add a team by pasting a GameChanger URL and selecting whether it is an owned (Lincoln) team or a tracked opponent
- Admin can view, edit, and deactivate teams from the admin interface
- Admin can assign teams to coaches (extending existing user_team_access)
- System can auto-discover opponents from a team's public schedule
- Crawl pipeline reads team configuration from the database, not YAML

## Non-Goals
- Authenticated API team discovery (the whole point is URL-based onboarding)
- Automatic crawling/scheduling (admin triggers crawls manually or via cron -- that's a separate concern)
- Player-level management in the admin UI (players come from crawled data)
- Removing `config/teams.yaml` entirely (it can remain as a bootstrap/seed mechanism)
- Season management UI (seasons are created by the data pipeline, not manually)
- Real-time opponent tracking notifications

## Success Criteria
- An admin can paste a GameChanger team URL, the system resolves it to a team name and location, and the team appears in the teams list
- An admin can mark a team as owned (Lincoln program) or tracked (opponent/scouting target)
- An admin can deactivate a team to stop it from being crawled
- An admin can see which opponents have been discovered from a team's schedule
- The crawl pipeline (`scripts/crawl.py`) reads active teams from the database when `config/teams.yaml` is absent or when a `--db` flag is used
- All admin team management pages are protected by the existing admin auth guard

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-042-01 | Schema migration: add public_id to teams | TODO | None | - |
| E-042-02 | URL parser and public API team resolver | TODO | None | - |
| E-042-03 | Admin team list and add-team page | TODO | E-042-01, E-042-02 | - |
| E-042-04 | Admin team edit and deactivate | TODO | E-042-03 | - |
| E-042-05 | Opponent auto-discovery from public schedule | TODO | E-042-03 | - |
| E-042-06 | Database-driven crawl configuration | TODO | E-042-01 | - |

## Technical Notes

### Schema Changes (Migration 005)
Add `public_id` column to the `teams` table:
```sql
ALTER TABLE teams ADD COLUMN public_id TEXT;
CREATE UNIQUE INDEX idx_teams_public_id ON teams(public_id) WHERE public_id IS NOT NULL;
```
- `public_id` is nullable: opponents discovered via authenticated endpoints (schedule `opponent_id`) may not have a `public_id` until resolved.
- Unique partial index ensures no duplicate `public_id` values while allowing multiple NULLs.
- No other schema changes needed -- the existing `teams` table already has `is_owned`, `is_active`, `source`, `level`, `last_synced`.

### GameChanger URL Patterns
The GC web app serves team pages at URLs like:
```
https://web.gc.com/teams/{public_id}/{url_encoded_name}
```
Example: `https://web.gc.com/teams/a1GFM9Ku0BbF/2025-summer-lincoln-rebels-14u`

The URL parser must:
1. Accept the full URL or just the `public_id` slug directly
2. Extract the `public_id` from the URL path (second segment after `/teams/`)
3. Validate the `public_id` format (short alphanumeric string, ~12 chars)
4. Handle edge cases: trailing slashes, query params, URL fragments

### Public API Integration
Team resolution uses `GET /public/teams/{public_id}` (no auth required). Returns:
- `name`, `sport`, `location` (city/state), `age_group`, `team_season` (season/year/record), `staff`, `avatar_url`
- The response `id` field IS the `public_id` (not a UUID). The internal UUID is NOT available from public endpoints.
- When adding a team via URL, we use the `public_id` as `team_id` in our database (since the UUID is not available from public endpoints). This is safe because `public_id` is unique and stable.

Opponent discovery uses `GET /public/teams/{public_id}/games` (no auth required). Returns:
- Game list with `opponent_team` object containing `name` and `public_team_profile_id` (the opponent's `public_id`)
- `game_stream_id` for box score access
- `home_team`/`away_team` indicator, final scores

### Admin UI Patterns
Follow the existing admin UI patterns from E-023:
- All routes under `/admin/` prefix
- `_require_admin()` guard on every route
- Jinja2 templates in `src/api/templates/admin/`
- DB helpers as synchronous functions called via `run_in_threadpool`
- Flash messages via query params (`?msg=` / `?error=`)
- Tailwind CDN for styling (same as existing admin pages)

### Admin UI Design (UX consultation)
- **Team list visual hierarchy**: Two sections on the teams page -- "Lincoln Program" (is_owned=1) at top, "Tracked Opponents" (is_owned=0) below. Each section is a separate table. This makes the page scannable at a glance. If either section is empty, show a placeholder message ("No opponents tracked yet -- use Discover Opponents on a Lincoln team").
- **Admin sub-navigation**: Add a simple horizontal nav bar at the top of all admin pages linking Users and Teams. Both pages currently lack sub-navigation -- this connects them.
- **URL input flow**: Direct submit (no preview step). The success flash message includes the resolved team name and location so the admin can verify. If the resolution is wrong, the edit page (E-042-04) provides correction. A two-step preview flow adds complexity without proportional value for a rarely-used admin action.
- **Opponent discovery results**: Flash message with count ("Discovered 8 new opponents for Lincoln Varsity"). Newly discovered opponents appear in the Tracked Opponents section with status "Inactive" -- visually clear. No separate results page needed.
- **Mobile considerations**: Admin pages are operator-focused (desktop primary). Standard form element sizes are fine -- no 44px touch target requirement. Basic readability on mobile is still good practice (responsive table wrappers).

### Route Structure
- `GET /admin/teams` -- Team list with add-team form
- `POST /admin/teams` -- Add team (accepts URL or public_id)
- `GET /admin/teams/{team_id}/edit` -- Edit team form
- `POST /admin/teams/{team_id}/edit` -- Update team
- `POST /admin/teams/{team_id}/deactivate` -- Toggle is_active
- `POST /admin/teams/{team_id}/discover-opponents` -- Trigger opponent discovery for a team

### URL Parser Notes (SE consultation)
- `urllib.parse.urlparse` is the right tool. The parser should accept any URL with `/teams/` in the path segment -- not just `web.gc.com`. Mobile share links, shortened URLs, or future domain changes should gracefully degrade to the fallback bare-slug check.
- Accept both `gc.com` and `web.gc.com` hostnames. Any URL with a `/teams/{slug}` path works.
- The `public_id` format is alphanumeric, typically 12 chars. The validation regex should be `^[A-Za-z0-9]{6,20}$` -- liberal enough to handle variations.

### public_id as team_id (DE + SE consultation)
Using `public_id` as `team_id` for URL-added teams is safe:
- `team_id` is `TEXT` PK -- no UUID validation anywhere in codebase (confirmed via grep).
- All FK references (`games.home_team_id`, `games.away_team_id`, `team_rosters.team_id`, etc.) are `TEXT REFERENCES teams(team_id)` -- format-agnostic.
- **Known limitation**: If the same team later appears via authenticated crawl (with its UUID), two rows would exist. This is out of scope for this epic. If it becomes a problem, a future merge/dedup story can address it. Document in the epic History.
- **Mitigation**: Since the project is shifting to URL-based onboarding (away from authenticated team discovery), the two-row scenario is unlikely in practice.

### Opponent Relationship Model (DE consultation)
The flat `teams` table with `is_owned=0` is sufficient. No explicit `team_opponents` relationship table is needed:
- Opponent relationships can be derived from the `games` table (any team appearing as opponent in a game involving an owned team).
- Adding a join table would add schema complexity without clear query benefit for the current use cases.
- If "which team discovered which opponent" tracking becomes needed, a `discovered_by_team_id` column on `teams` would be simpler than a join table.

### Crawl Configuration Migration
Currently `scripts/crawl.py` reads `config/teams.yaml` via `src/gamechanger/config.py`. The new flow:
- Add a `load_config_from_db()` function that queries `SELECT * FROM teams WHERE is_active = 1`
- `scripts/crawl.py` accepts a `--source db|yaml` flag (default: `yaml` for backward compat)
- When `--source db`: load team config from SQLite, build `CrawlConfig` equivalent
- `config/teams.yaml` remains as a bootstrap/seed mechanism but is no longer the primary source

### File Organization
- **Routes**: `src/api/routes/admin.py` -- extend with team management routes (existing file)
- **URL parser**: `src/gamechanger/url_parser.py` -- new module for GC URL parsing
- **Team resolver**: `src/gamechanger/team_resolver.py` -- new module for public API team resolution
- **DB queries**: `src/api/db.py` -- add team management query functions
- **Templates**: `src/api/templates/admin/teams.html`, `edit_team.html` -- new templates
- **Migration**: `migrations/005_teams_public_id.sql`
- **Tests**: `tests/test_admin_teams.py` (new), `tests/test_url_parser.py` (new), `tests/test_team_resolver.py` (new)

### Existing Admin Integration
The teams list in the user management page (`/admin/users`) shows team checkboxes from `_get_owned_teams()`. After this epic, that function should show all managed teams (owned + tracked with `is_active = 1`), not just `is_owned = 1`. This is a minor update to the existing user management flow.

### Execution Order and File Conflicts (SE consultation)
Stories 03, 04, and 05 all modify `src/api/routes/admin.py`, `src/api/db.py`, and `src/api/templates/admin/teams.html`. To avoid merge conflicts:

1. **E-042-01** first (no file conflicts).
2. **E-042-02 + E-042-06 in parallel** -- E-042-02 creates new files only (`url_parser.py`, `team_resolver.py`); E-042-06 modifies `config.py` and scripts. No overlap.
3. **E-042-03** next -- creates `teams.html`, extends `admin.py` and `db.py`.
4. **E-042-04 + E-042-05 in parallel** -- both modify `admin.py`, `db.py`, and `teams.html`, BUT: E-042-04 adds edit/toggle routes (append pattern), E-042-05 adds discover route (append pattern). Both append new functions at END of each file. Safe for parallel if agents follow append discipline. **If agents struggle with parallel edits, dispatch sequentially: 04 then 05.**

E-042-05's dependency was updated from (01, 02) to (03) because it modifies `teams.html` which E-042-03 creates, and it needs the team list infrastructure to render the discover button.

### Synchronous API Calls in Admin Routes (SE consultation)
The POST handler for adding a team calls `resolve_team()` synchronously inside `run_in_threadpool`. This is acceptable:
- Admin actions are infrequent (adding a team is done a handful of times per season).
- The existing admin pattern uses `run_in_threadpool` for all DB work.
- `httpx` synchronous client inside `run_in_threadpool` avoids async complexity.
- Timeout: set a 10-second timeout on the HTTP call to avoid hanging on API issues.

### Testing Strategy
- Unit tests for URL parser (various URL formats, edge cases)
- Unit tests for team resolver (mock HTTP responses)
- Route tests using FastAPI TestClient with in-memory SQLite
- Test admin auth guard on all new routes (403 for non-admin, redirect for unauthenticated)
- Mock the public API calls in route tests

## Open Questions
All resolved during expert consultation. See History.

## History
- 2026-03-05: Created as DRAFT. Expert consultation pending (UX designer, data-engineer, software-engineer).
- 2026-03-05: **Expert consultation completed.** Three experts consulted (UX designer, software-engineer, data-engineer). Key changes:
  - **UX**: Two-section team list (Lincoln Program / Tracked Opponents). Admin sub-nav linking Users and Teams pages. Direct submit for URL input (no preview step). Flash message for opponent discovery results.
  - **SE**: URL parser liberal acceptance pattern (any URL with `/teams/` path). E-042-05 dependency changed from (01, 02) to (03) to avoid file conflicts on `teams.html`. Synchronous API calls via `run_in_threadpool` confirmed acceptable. 10-second HTTP timeout recommended.
  - **DE**: Migration 005 approach validated (ALTER TABLE + partial unique index). public_id-as-team_id confirmed safe (TEXT PK, no UUID assumptions in codebase). Flat teams table sufficient for opponent model (no join table needed). Season derivation query improved to `ORDER BY year DESC LIMIT 1` with note about multi-season ambiguity.
  - **Open questions resolved**: (1) URL pattern: parser is liberal, accepts any `/teams/{slug}` URL. (2) Opponent discovery: explicit admin action (button click). (3) Discovered opponents: `is_active=0` default (admin enables manually).
  - **Known limitation documented**: Same team could exist as two rows if added via URL (public_id as team_id) and later via authenticated crawl (UUID as team_id). Out of scope -- merge/dedup is a future concern if the project returns to authenticated crawling.
- 2026-03-05: Set to READY after quality checklist passed.
