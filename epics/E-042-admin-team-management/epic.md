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

**Expert consultation completed:** UX designer (admin UI layout, team list visual hierarchy, URL input flow), data-engineer (migration 005 validation, public_id-as-team_id soundness, opponent model, season derivation), software-engineer (URL parser feasibility, file conflict assessment, sync API call pattern, crawl script integration), api-scout (confirmed public games endpoint lacks opponent identifiers -- name-only discovery, added during codex spec review triage 2026-03-06).

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
- The crawl pipeline (`scripts/crawl.py`) reads active teams from the database when the `--source db` flag is used (YAML remains the default)
- All admin team management pages are protected by the existing admin auth guard

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-042-01 | Schema migration: add public_id to teams | TODO | None | - |
| E-042-02 | URL parser and public API team resolver | TODO | None | - |
| E-042-03 | Admin team list and add-team page | TODO | E-042-01, E-042-02 | - |
| E-042-04 | Admin team edit and deactivate | TODO | E-042-03 | - |
| E-042-05 | Opponent auto-discovery from public schedule | TODO | E-042-02, E-042-03, E-042-04 | - |
| E-042-06 | Database-driven crawl configuration | TODO | None | - |

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
- Game list with `opponent_team` object containing `name` (always present) and optionally `avatar_url`. **No opponent identifier is available** -- no `public_id`, no UUID (confirmed API limitation, see `docs/gamechanger-api.md` Known Limitations).
- `game_stream_id` for box score access
- `home_team`/`away_team` indicator, final scores

**Implication for opponent discovery (E-042-05)**: Opponents are discovered by name only. E-042-05 creates placeholder records (`public_id=NULL`, `source='discovered'`). The admin pastes opponent URLs via the add-team form to fully onboard them with a `public_id`.

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
- `POST /admin/teams/{team_id}/toggle-active` -- Toggle is_active
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
- Add a `load_config_from_db()` function that queries `SELECT team_id, name, level FROM teams WHERE is_active = 1 AND is_owned = 1`
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
The teams list in the user management page (`/admin/users`) shows team checkboxes from `_get_owned_teams()`. Currently it only shows `is_owned = 1` teams. **Follow-up (not in scope for this epic):** Once team management is battle-tested, consider expanding this function to show all managed teams (owned + tracked with `is_active = 1`) so coaches can be granted access to opponent scouting data. No story in this epic modifies `_get_owned_teams()`.

### Execution Order and File Conflicts (SE consultation)
Stories 03, 04, and 05 all modify `src/api/routes/admin.py`, `src/api/db.py`, and `src/api/templates/admin/teams.html`. To avoid merge conflicts:

1. **E-042-01 + E-042-02 + E-042-06 in parallel** -- E-042-01 creates migration 005 (new file). E-042-02 creates new files only (`url_parser.py`, `team_resolver.py`). E-042-06 modifies `config.py` and scripts. No overlap between any of these three.
2. **E-042-03** next -- creates `teams.html`, extends `admin.py` and `db.py`. Blocked by E-042-01 (schema) and E-042-02 (resolver).
3. **E-042-04** next -- extends `admin.py`, `db.py`, `teams.html`. Blocked by E-042-03.
4. **E-042-05** last -- extends `admin.py`, `db.py`, `teams.html`, `team_resolver.py`. Blocked by E-042-04 (file conflict on shared files) and E-042-02 (team_resolver.py).

E-042-04 and E-042-05 are now sequential (not parallel) because both modify the same four files (`admin.py`, `db.py`, `teams.html`, `test_admin_teams.py`). This eliminates merge conflict risk.

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
- 2026-03-06: **Codex spec review triage.** 6 findings (3 P1, 3 P2). Fixed 5, deferred 1:
  - FIXED P1: E-042-06 AC-5 `DB_PATH` -> `DATABASE_PATH` (matches canonical env var in src/api/db.py).
  - FIXED P1: E-042-05 missing dependency on E-042-02 (team_resolver.py created by 02, extended by 05). Added to story and epic table.
  - DEFERRED P1: bootstrap.py DB mode -- bootstrap.py is out of scope for this epic. It wraps crawl.py/load.py which get `--source db`. Bootstrap DB-mode support is a future enhancement (IDEA-012 scope).
  - FIXED P2: Epic success criteria `--db flag` -> `--source db` (aligns with E-042-06 AC-4 contract).
  - FIXED P2: Epic route map `/deactivate` -> `/toggle-active` (aligns with E-042-04 AC-8 -- route both activates and deactivates).
  - FIXED P2: E-042-01 Blocks list removed E-042-02 (URL parser/resolver are DB-independent; E-042-02 creates new files only, no schema dependency). E-042-02 remains correctly listed as having no dependencies in both story and epic table.
- 2026-03-06: **Codex spec review triage #2.** 11 sub-findings across 9 categories. api-scout consulted. Decisions:
  - **REFINE (7 changes applied):**
    - E-042-02: Added AC-11 (malformed 200 response raises `GameChangerAPIError`), renumbered AC-12 (tests). Closes Finding 1a.
    - E-042-06 AC-8: Clarified which ACs load.py mirrors (AC-4 through AC-7). Closes Finding 1b.
    - E-042-03 Blocks: Added E-042-05 (asymmetric dependency fix). Closes Finding 2a.
    - E-042-06: Removed E-042-01 dependency (load_config_from_db doesn't use public_id). E-042-01 Blocks updated. Epic table updated. Closes Finding 2b.
    - E-042-04+05: Made sequential (05 blocked by 04) due to shared file conflicts on admin.py, db.py, teams.html, test_admin_teams.py. Epic execution order rewritten. Closes Finding 3.
    - E-042-05: **Major revision** -- rewrote story for name-only opponent discovery. API spec confirms `opponent_team` contains only `name` + optional `avatar_url`; no opponent identifier available. Discovered opponents are now placeholders (`public_id=NULL`, `source='discovered'`). Admin pastes opponent URLs to fully onboard. Epic Technical Notes corrected. Closes Finding 7.
    - Epic Technical Notes: Crawl config query corrected to `WHERE is_active = 1 AND is_owned = 1`. `_get_owned_teams()` expansion marked as follow-up. Closes Findings 9a, 9b.
  - **DISMISS (2 findings):**
    - Finding 1c (E-042-01 AC-8/AC-4 testability): AC-4 is the functional requirement, AC-8 is the test approach. Standard migration test pattern. No ambiguity.
    - Finding 4 (E-042-03 AC-4 edit links): Rendering a link to a future route is normal incremental development. Story is a complete vertical slice.
  - **New dispatch order:** 01+02+06 parallel -> 03 -> 04 -> 05 (fully sequential for shared-file stories).
- 2026-03-06: **Codex code review fixes.** 3 findings (P1, P2, P5):
  - FIXED P1: E-042-03 add-team handler now checks for discovered placeholders (name match, `source='discovered'`, `public_id IS NULL`) and upgrades the existing row instead of creating a duplicate. AC-9 and AC-14 updated.
  - FIXED P2: E-042-03 AC-17 now includes a test for the placeholder-to-resolved upgrade path.
  - FIXED P5: PM memory dispatch order corrected to match current epic (01+02+06 parallel -> 03 -> 04 -> 05).
