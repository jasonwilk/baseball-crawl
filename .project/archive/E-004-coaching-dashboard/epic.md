# E-004: Coaching Dashboard

## Status
`COMPLETED`

## Overview
Build the coach-facing dashboard: five server-rendered HTML views that let coaches review team stats, scout opponents, track players across seasons, and review game logs -- all from a phone in the dugout, without writing SQL or running scripts.

## Background & Context
The data pipeline is complete (E-002 crawlers + loaders, E-003 schema). Auth is complete (E-023 magic link + passkey + team-scoped access). A minimal `/dashboard` route already exists showing basic batting stats (name, AB, H, BB, SO) with a team selector. This epic replaces that skeleton with a full set of coaching views.

**Blockers cleared**: E-002 (COMPLETED), E-003 (COMPLETED), E-023 (COMPLETED).

**What already exists** (from E-023/E-009):
- `src/api/routes/dashboard.py` -- single route `GET /dashboard` with team selector and auth integration
- `src/api/db.py` -- `get_team_batting_stats()` (minimal: name, ab, h, bb, so), `get_teams_by_ids()`, `get_connection()`, `check_connection()`
- `src/api/templates/base.html` -- Tailwind CDN base layout with nav bar ("LSB Baseball" + "Team Stats" link)
- `src/api/templates/dashboard/team_stats.html` -- minimal batting stats table
- `src/api/auth.py` -- SessionMiddleware attaching `request.state.user` and `request.state.permitted_teams`
- `src/api/main.py` -- app factory with router registration and static file mount

**Expert consultation**: No separate expert consultation required -- coaching data requirements are well-documented in CLAUDE.md Key Metrics section and `docs/gamechanger-stat-glossary.md`. Schema capabilities are fully known from E-003. Auth model is fully known from E-023.

**Open questions resolved**:
- **Team selector vs. separate dashboards**: Single dashboard with team selector (already implemented in E-023).
- **URL structure**: Auth-protected via SessionMiddleware (already implemented in E-023). Cloudflare Zero Trust in production.
- **Data refresh**: On-demand via `scripts/crawl.py` + `scripts/load.py`. Dashboard reads whatever is in SQLite.
- **Analytical views coaches want most**: Batting stats, pitching stats, opponent scouting, player profiles, game logs (from CLAUDE.md Key Metrics).

## Goals
- Enhance the existing `/dashboard` batting stats page with full stat columns and computed rates (AVG, OBP, SLG)
- Add a team pitching stats page with computed rates (ERA, K/9, BB/9, WHIP)
- Add an opponent scouting report page showing opponent batting + pitching leaders
- Add a player profile page showing career stats across teams and seasons
- Add a game log page showing scores and per-game player lines
- All views mobile-friendly (375px minimum), navigable via a shared nav bar

## Non-Goals
- Data entry or editing (read-only dashboard)
- Push notifications or real-time updates
- Advanced analytics (WAR, BABIP, wRC+) -- stick to standard stats coaches understand
- Automated lineup optimization
- Client-side JavaScript (server-rendered only for MVP)
- Split data display (home/away, L/R) -- splits are in the DB but add complexity; defer to a follow-up epic

## Success Criteria
- A coach can see all batters on their team with AVG, OBP, SLG, and traditional counting stats
- A coach can see all pitchers on their team with ERA, K/9, BB/9, and counting stats
- A coach can pull up an upcoming opponent and see their top hitters and pitchers
- A coach can click on any player and see their stats broken down by season and team
- A coach can review game-by-game results with per-player batting and pitching lines
- All views render correctly at 375px width without horizontal scrolling on the primary content
- Bottom nav bar allows one-tap navigation between the four top-level views (batting, pitching, games, opponents); player profiles are reached via player name links within those views

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-004-01 | Navigation shell and base layout | DONE | None | - |
| E-004-02 | Enhanced team batting stats | DONE | E-004-01 | - |
| E-004-03 | Team pitching stats page | DONE | E-004-01 | - |
| E-004-04 | Game log page | DONE | E-004-01 | - |
| E-004-05 | Opponent scouting report | DONE | E-004-01 | - |
| E-004-06 | Player profile page | DONE | E-004-01 | - |

## Technical Notes

### Existing Infrastructure
- **Auth**: SessionMiddleware populates `request.state.user` (dict with `user_id`, `email`, `display_name`, `is_admin`) and `request.state.permitted_teams` (list of team_id strings). All dashboard routes are auth-protected automatically.
- **Team selector**: Already implemented -- `?team_id=` query param with validation against permitted teams. Reuse this pattern in every team-scoped view.
- **Database**: `src/api/db.py` provides `get_connection()` returning a SQLite connection with WAL mode and FK enforcement. All new query functions go here.
- **Templates**: Jinja2 via `src/api/templates/`. Base template at `base.html`. Dashboard templates in `dashboard/` subdirectory.
- **CSS**: Tailwind CDN (`<script src="https://cdn.tailwindcss.com">`). No build step.
- **Static files**: Mounted at `/static` from `src/api/static/`.

### ip_outs Display Convention
Innings pitched are stored as integer outs (1 IP = 3 outs, 6.2 IP = 20 outs). The display layer must convert: `ip_outs // 3` whole innings + `ip_outs % 3` fraction. Display as "6.2" not "6.67". This conversion should be a Jinja2 filter or a Python helper used by all templates that show IP.

### Computed Stats
All computed stats are calculated at query time or in the template, not stored in the database:
- **AVG**: h / ab (display as .000 format, e.g., ".333")
- **OBP**: (h + bb) / (ab + bb) -- simplified; HBP and SF not in our schema
- **SLG**: (h - doubles - triples - hr + 2*doubles + 3*triples + 4*hr) / ab = (h + doubles + 2*triples + 3*hr) / ab
- **ERA**: (er * 9) / (ip_outs / 3) = (er * 27) / ip_outs (since ip_outs = IP * 3, and ERA = ER*9/IP)
- **K/9**: (so * 9 * 3) / ip_outs = (so * 27) / ip_outs
- **BB/9**: (bb * 27) / ip_outs
- **WHIP**: (bb + h) * 3 / ip_outs

Handle division by zero gracefully -- display "-" when denominator is 0.

### Route Structure
All dashboard routes live under `/dashboard/`:
- `GET /dashboard` -- team batting stats (existing, enhanced)
- `GET /dashboard/pitching` -- team pitching stats
- `GET /dashboard/games` -- game log with scores
- `GET /dashboard/games/{game_id}` -- single game detail with box score
- `GET /dashboard/opponents` -- opponent list
- `GET /dashboard/opponents/{team_id}` -- opponent scouting report
- `GET /dashboard/players/{player_id}` -- player profile

All routes accept `?team_id=` for team scoping (except player profile -- see below). All routes accept `?season_id=` with a default of the current year's spring-hs season. The opponent detail route (`/dashboard/opponents/{team_id}`) requires the opponent to appear in games for at least one of the user's permitted teams. The player profile route (`/dashboard/players/{player_id}`) requires the player to appear on at least one of the user's permitted teams (current or historical roster entry); this supports cross-level tracking (freshman -> JV -> varsity) while maintaining team-scoped authorization.

### File Organization
- **Routes**: `src/api/routes/dashboard.py` -- all dashboard routes in one file (it's small enough)
- **DB queries**: `src/api/db.py` -- all query functions
- **Templates**: `src/api/templates/dashboard/` -- one template per view
- **Tests**: `tests/test_dashboard.py` -- route tests using FastAPI TestClient (existing location; do not move)

### Mobile-First Design Principles
- Tables use `overflow-x-auto` wrapper for horizontal scroll on narrow screens
- **Column ordering**: Rate stats and key decision-making stats appear in the leftmost columns after Player name so they are visible at 375px without scrolling. For batting: Player, AVG, OBP, GP, BB, SO (then SLG, H, AB, 2B, 3B, HR, SB, RBI). For pitching: Player, ERA, K/9, BB/9, WHIP (then GP, IP, H, ER, BB, SO, HR). Coaches use walk rate and strikeout rate as primary development indicators; RBI is lineup-dependent and placed last. Counting stats follow to the right and may require horizontal scroll on narrow screens.
- Player names are clickable links to profile pages
- Team selector appears at top of every team-scoped page
- Use Tailwind responsive prefixes (`sm:`, `md:`) sparingly -- design for mobile first
- **Touch targets**: All interactive elements (nav links, team selector pills, table row links) must be at minimum 44px tap height. Team selector pills use `py-2` not `py-1`. This is a dugout-use requirement -- coaches tap with gloved or dirty hands.
- **Contrast**: Avoid `text-gray-400` or `text-gray-500` for any text content. Minimum is `text-gray-600` for secondary text, `text-gray-900` for primary. Coaches view screens in direct sunlight.
- **Sticky table headers**: Use `sticky top-0` on `<thead>` elements so column headers remain visible when scrolling long stat tables.
- **Collapsible sections**: Use native `<details>/<summary>` HTML elements (no JavaScript) when a page has multiple data-heavy sections (e.g., box score with 4 tables). This keeps pages scannable on mobile without hiding data.
- **Navigation pattern**: Bottom fixed nav bar for the 4 main sections (Batting, Pitching, Games, Opponents). Top bar reserved for branding ("LSB Baseball") and user info (display name, logout). Bottom nav uses icons + labels and provides 44px+ touch targets. This is the standard mobile dashboard pattern -- thumb-reachable navigation for frequent section switching.

### Season Selection
The current default logic (`f"{datetime.date.today().year}-spring-hs"`) is correct for the primary use case. All team-scoped routes accept an optional `?season_id=` query parameter to override the default. If provided and non-empty, use it; otherwise fall back to the computed default. This pattern is established in E-004-01 and reused by all subsequent stories.

### Test Fixture Alignment
The existing test file at `tests/test_dashboard.py` uses a simplified schema that is out of sync with the real schema in `migrations/001_initial_schema.sql`. Key discrepancies: `team_rosters.season` (TEXT) should be `season_id` (FK to seasons), `games.season` (TEXT) should be `season_id` (FK to seasons), `seasons` table is missing entirely. E-004-01 must update the test fixture schema to match the real migration so that subsequent stories can join on `season_id` and `seasons` correctly. The test file stays at `tests/test_dashboard.py` (not moved to `tests/api/`).

### Coaching Workflow Context
Coaches use this dashboard in three modes: (1) **Pregame** -- opponent scouting report is the primary tool, accessed the night before a game. The Key Players card and Last Meeting summary provide the quick-glance pregame view. (2) **In-game (dugout)** -- quick micro-lookups on a phone between innings. Must be sub-5-second to answer. (3) **Postgame/weekly** -- game detail review and player development tracking. Design for the pregame and dugout modes first; they are the most time-constrained.

### Execution Order and File Conflicts
Stories 02-06 all append to `src/api/db.py`, `src/api/routes/dashboard.py`, and `tests/test_dashboard.py`. **Recommended dispatch order** (SE-reviewed):

1. **E-004-01** first (sole dependency for all others).
2. **E-004-02 + E-004-03 in parallel** -- batting enhances an existing function while pitching adds a new function. Safe if both agents follow the append discipline: new functions at END of `db.py`, new routes at END of `dashboard.py`, new test classes at END of `test_dashboard.py`. E-004-02's interior edit (updating `get_team_batting_stats`) is isolated from E-004-03's append.
3. **E-004-04** next -- game tables are structurally different; clean merged state from 02+03.
4. **E-004-05** after 04 -- Last Meeting card queries `games` table (same as 04); test fixture patterns established.
5. **E-004-06** last -- player profile is the most complex DB function; benefits from all prior stories' patterns in `db.py` and `dashboard.py` being in final stable state.

**Story sizing (SE-reviewed)**: E-004-05 (18 ACs) and E-004-06 (16 ACs) are at the upper bound but do NOT need splitting. Each is a coherent single-page deliverable where splitting would create broken partial pages and more coordination overhead than it saves.

### Testing Strategy
- Each story includes route-level tests using FastAPI TestClient
- Tests use an in-memory SQLite database with seeded test data
- Test that routes return 200 with valid data, handle empty results, and enforce permissions (403 for unauthorized team_id on team-scoped routes, 403 for unauthorized opponent on scouting detail, 403 for unauthorized player on player profile)
- Mock `src.api.db.get_connection` to use the test database

## History
- 2026-02-28: Created as DRAFT; blocked on E-002 and E-003 completion
- 2026-03-04: Refined with 6 stories. Blockers cleared (E-002, E-003, E-023 all COMPLETED). Open questions resolved. Set to READY.
- 2026-03-05: **UX refinement pass.** Applied mobile-first UX recommendations to epic Technical Notes and all 6 stories. Key changes: (1) bottom fixed nav bar pattern for main sections instead of top-bar links; (2) reordered table columns to put rate stats (AVG, ERA) leftmost for 375px visibility; (3) added 44px touch target requirement for all interactive elements; (4) added sunlight-readable contrast minimums (text-gray-600); (5) added sticky table headers; (6) added `<details>/<summary>` collapsible sections for data-heavy pages; (7) added "Key Players" callout to opponent scouting report; (8) added "Current Season Summary" card to player profile.
- 2026-03-05: **Codex review remediation.** Addressed 4 findings.
  - **Finding 1 (P1, FIXED)**: ERA formula bug. `(er * 9) / ip_outs` was wrong; corrected to `(er * 27) / ip_outs`. Fixed in epic Technical Notes and E-004-03 AC-4 reference.
  - **Finding 2 (P2, FIXED)**: Missing 403 test for opponent detail. Added AC-14 to E-004-05 requiring 403 when opponent is not associated with any of the user's permitted teams. Updated epic route structure notes.
  - **Finding 3 (P3, FIXED)**: Player profile auth bypass. E-004-06 AC-10 said "any authenticated user can view any player profile," conflicting with E-023 team-scoped auth. Revised to require the player to appear on at least one of the user's permitted teams (current or historical roster). Supports cross-level tracking while maintaining auth model consistency. Added AC-15 for 403 test.
  - **Finding 4 (P5, FIXED)**: Nav inconsistency. Epic said "five views" in nav but E-004-01 only defined four nav links. Clarified: four top-level nav items (batting, pitching, games, opponents); player profiles are detail views reached via player name links, not nav items.
- 2026-03-05: **Coach + UX + SE refinement pass.** UX designer interviewed coach about real coaching workflows (pregame, dugout, postgame, player development). SE reviewed technical feasibility against codebase. Key changes:
  - **Batting column reorder (E-004-02)**: BB and SO moved into 375px visible zone as primary development indicators. RBI moved to end (lineup-dependent, coaches discount it).
  - **Enhanced Key Players card (E-004-05)**: Best pitcher now shows K rate and avg pitch count alongside ERA. Best hitter threshold clarified.
  - **Last Meeting card (E-004-05)**: New AC -- opponent scouting shows the most recent game result against this opponent for quick rematch context.
  - **Next game date on opponent list (E-004-05)**: New AC -- opponent list shows next scheduled game date for prep triage.
  - **Season selector support (all stories)**: Added `?season_id=` query param support across all team-scoped routes.
  - **Test fixture alignment (E-004-01)**: Existing test schema at `tests/test_dashboard.py` must be updated to match real migration schema (season_id FKs, seasons table).
  - **SE implementer notes**: CASE expression for opponent name resolution (E-004-04), two-way player edge case in Recent Games (E-004-06), active_team_id for box score details-open default (E-004-04).
  - **Deferred**: Handedness/B-T indicator (schema lacks bats/throws data -- needs crawler+migration), recent form indicator (per-game aggregation complexity), player comparison view (future epic), pregame summary page (future epic).
- 2026-03-05: **Codex spec review remediation (2nd round).** Addressed 2 P1, 7 P2, 2 P3 findings.
  - **P1 FIXED**: Added `?season_id=` override ACs and 403-for-unauthorized-team_id ACs to E-004-03, E-004-04, E-004-05 list routes. All team-scoped routes now have explicit auth + season_id behavior.
  - **P2 FIXED**: E-004-01 AC-5 reworded to not conflict with AC-9 (season_id addition). E-004-06 AC-13 "key stats" fully specified (AB-H batting line, IP/ER/SO pitching line). E-004-02 AC-10 test assertions specified. Cross-link 404 notes added to E-004-05/06 for game detail links (no hard dependency on E-004-04 needed). Updated dispatch order to SE-reviewed sequence: 01 -> 02+03 parallel -> 04 -> 05 -> 06.
  - **P2 ASSESSED, NO SPLIT**: E-004-05 (18 ACs) and E-004-06 (16 ACs) reviewed with SE -- both are coherent single-page deliverables; splitting creates more coordination overhead than it saves.
  - **P3 FIXED**: E-004-01 description corrected from "five sections" to "four sections."
- 2026-03-05: **Dispatch and implementation.** All 6 stories executed in sequence: 01 -> 02+03 parallel -> 04 -> 05 -> 06. Dispatch order matched SE-reviewed plan. 02+03 parallel dispatch succeeded with no merge conflicts (interior edit vs append discipline). 123 tests pass across test_dashboard.py and test_helpers.py.
- 2026-03-05: **Codex code review remediation.** 1 P1 + 2 P2 findings fixed: (1) opponent list links now pass `?team_id=` for multi-team context preservation, (2) `format_date` Jinja2 filter added for "Mar 4" date display across all templates, (3) two placeholder test methods replaced with real assertions.
- 2026-03-05: **COMPLETED.** All 6 stories DONE, all ACs verified, 123 tests pass. No documentation impact (no new admin/deployment/API changes). Archived.
