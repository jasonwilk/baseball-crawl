# E-173: Fix Opponent Scouting Workflow End-to-End

## Status
`READY`

## Overview
Fix the broken opponent scouting workflow so that resolving an opponent in the admin UI causes stats to appear in the dashboard. Currently, resolution updates `opponent_links` but never propagates to `team_opponents` (which the dashboard queries), leaving coaches with empty scouting reports. This epic fixes the data disconnect, auto-triggers scouting after resolution, unifies the fragmented admin workflow, and replaces pipeline jargon with plain English throughout.

## Background & Context

The user has been unable to get opponent scouting data to display for over a week. The root cause is a data layer disconnect between two tables that were never synchronized:

- **`opponent_links`** tracks resolution state (root_team_id -> resolved_team_id + public_id). Updated by the opponent resolver (auto) and admin resolve/connect handlers (manual).
- **`team_opponents`** is the junction table the dashboard queries to list opponents. Populated by the schedule loader at game-load time using stub team IDs.
- **Neither resolution path** (auto or manual) propagates `resolved_team_id` back to `team_opponents`. Stats load for the resolved team (e.g., team 44), but the dashboard shows the stub team (e.g., team 27) with no stats.

Additionally, the admin workflow requires 5 manual steps across 3 UI surfaces + CLI: sync -> discover -> resolve/connect -> CLI scout. Coaches expect: schedule loads -> data appears -> click opponent -> scouting report.

**Expert consultations (all completed):**
- **baseball-coach**: Coaches think schedule-first ("who do we play next?"). Sort by next game date. Three clear data states (loaded/syncing/no profile). Zero admin terminology in dashboard.
- **data-engineer**: Root cause confirmed. Resolution must be a write-through operation: propagate to `team_opponents`, set `is_active=1`.
- **software-engineer**: Auto-scout via BackgroundTask is feasible. `run_scouting_sync` already designed for this. Shared `finalize_resolution()` function recommended.
- **ux-designer**: Collapse 5 steps to 2. Merge resolve+connect into "Find on GC" page. Auto-discover after sync. Dashboard sort by next_game_date with data status indicators.
- **baseball-coach walkthrough**: Audited all 7 opponent-related templates. Found jargon in empty states, missing data status indicators, confusing resolve/connect split, "tracked" badge should say "Opponent."

**Absorbs E-171 scope**: The search result enrichment from E-171-resolve-search-enrichment (season year prominence, player count, staff names in search results) is incorporated into Story 03's unified resolve page design.

## Goals
- Resolving an opponent in the admin UI causes scouting stats to appear in the dashboard without further manual steps
- The admin workflow for opponent management is reduced from 5 steps to 2 (sync team, resolve unknowns)
- Dashboard opponent list is sorted by next game date with clear data-availability indicators
- All pipeline jargon ("Discover", "Sync", "Scout", "Resolve", "Connect") is replaced with plain English or made invisible

## Non-Goals
- Duplicate team cleanup (61 -> ~20 reduction) -- existing `bb data dedup` handles this; E-167's `ensure_team_row()` prevents new duplicates
- Scoresheet-only data display for unlinked opponents (showing box score data from our games) -- future epic
- Dashboard content enhancements (recent form, lineup order, pitcher rest, print layout improvements) -- future epic
- Batch resolve (resolving multiple opponents at once) -- current one-at-a-time flow is fine for 10-20 opponents per season
- Changes to the scouting pipeline itself (crawlers, loaders) -- only wiring the trigger

## Success Criteria
- An operator can resolve an opponent and see scouting stats in the dashboard within minutes, with no CLI commands
- The admin opponents page uses consistent, plain-English terminology
- The dashboard opponent list defaults to upcoming-game-first sort order
- Each dashboard opponent row shows a data availability indicator (stats loaded / syncing / no profile)
- The "Discover Opponents" button is removed (discovery is automatic after member sync)
- Resolve and Connect flows are merged into a single page

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-173-01 | Resolution write-through to team_opponents | TODO | None | - |
| E-173-02 | Auto-scout after resolution | TODO | E-173-01 | - |
| E-173-03 | Unified resolve page (Find on GC) | TODO | E-173-01, E-173-02 | - |
| E-173-04 | Dashboard opponent sort and data status | TODO | E-173-01 | - |
| E-173-05 | Admin and dashboard terminology cleanup | TODO | E-173-03, E-173-04 | - |
| E-173-06 | One-time opponent data repair command | TODO | E-173-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Resolution Write-Through Pattern

When any resolution path succeeds (search resolve, manual connect, or auto-resolver), a shared function must atomically perform five operations:

1. **Discover the old stub**: Query `team_opponents JOIN teams` for a tracked team matching `opponent_name` under `our_team_id` (same pattern as existing `_find_tracked_stub()` in db.py). If found and differs from `resolved_team_id`, this is the stub to replace.
2. **Upsert `team_opponents`**: Link `our_team_id` to `resolved_team_id`. If the old stub row exists and the resolved team already has a `team_opponents` row, delete the stub row (avoiding UNIQUE constraint violation); otherwise update the stub row to point to the resolved team.
3. **Activate the team**: `UPDATE teams SET is_active = 1 WHERE id = resolved_team_id`. Resolution is an explicit admin action implying intent to scout.
4. **Reassign FK references**: When an old stub is discovered and differs from `resolved_team_id`, reassign all FK references from the stub to the resolved team: `games.home_team_id`/`away_team_id`, `player_game_batting.team_id`, `player_game_pitching.team_id`, `player_season_batting.team_id`, `player_season_pitching.team_id`, `spray_charts.team_id`, `team_rosters.team_id`. Skip rows where the resolved team already has a matching record to avoid duplicates.
5. **Return a result dict** with `resolved_team_id`, `public_id` (read from the resolved team row), and `old_stub_team_id` (the discovered stub's team ID if one was replaced, else None) so the caller can decide whether to trigger scouting.

This function belongs in `src/api/db.py` alongside the existing resolution functions. All three resolution paths must call it with `(conn, our_team_id, resolved_team_id, opponent_name, first_seen_year)`: `resolve_opponent_confirm` (search resolve, admin.py ~line 2855), `save_manual_opponent_link` (manual connect, db.py ~line 1283, called internally before commit), and `OpponentResolver.resolve()` (auto-resolver, opponent_resolver.py). The function discovers the old stub internally -- callers do not need to determine it.

### TN-2: Auto-Scout Trigger

After resolution succeeds and `public_id` is non-null, enqueue `run_scouting_sync` as a FastAPI `BackgroundTask`:

1. Create a `crawl_jobs` row (same pattern as admin sync route, admin.py ~line 2305-2315)
2. Call `background_tasks.add_task(trigger.run_scouting_sync, team_id, public_id, crawl_job_id)`
3. If `public_id` is null, soft-skip (log a warning, don't error)

The admin resolve handler already has access to `BackgroundTasks` via FastAPI injection. The connect handler may need it added as a parameter.

### TN-3: Dashboard Data Status

Three states for each opponent row in the dashboard opponent list:

| State | Condition | Dashboard Display |
|-------|-----------|-------------------|
| Stats loaded | `player_season_batting` or `player_season_pitching` rows exist for this team+season | Green dot, "Stats" label on wider screens |
| Syncing | `crawl_jobs` row exists with `status = 'running'` for this team | Yellow dot, "Syncing" label |
| No profile | Neither of the above (unlinked or linked but no data) | Gray dash, "Scoresheet" label |

The `get_team_opponents()` query needs a LEFT JOIN or subquery to determine data status per opponent.

### TN-4: Unified Resolve Page Layout

The merged resolve page combines search (primary, top) and URL paste (fallback, below divider) into a single page titled "Find [opponent] on GameChanger". Layout:

1. **Search section** (top): Team name input, state filter, city input, Search button. Results show cards with: team name (bold), season year (prominent badge), location, player count, staff names (per E-171 enrichment). Select button per card.
2. **Divider**: "-- or --"
3. **URL paste section** (below): Input field for GameChanger URL, "Look up" button.
4. **Skip section** (bottom, de-emphasized): "No match -- skip" as gray text link.

Both paths lead to the same confirm step, which triggers auto-scout on success.

Search result card fields (absorbing E-171 scope): `name` (bold), `season_year` (prominent badge, NOT tiny gray text), `city`/`state` (secondary), `num_players` (e.g., "14 players"), `staff` (smallest text, comma-separated). All fields already available in the normalized search result dict from `_gc_search_teams()`.

### TN-5: Terminology Mapping

| Current Term | New Admin Term | Dashboard Term |
|-------------|---------------|----------------|
| Discover Opponents | *(removed -- automatic)* | *(invisible)* |
| Resolve | Find on GameChanger | *(invisible)* |
| Resolved / Unresolved (badge) | *(replaced by pipeline status: Needs linking / Syncing / Stats loaded / Sync failed / Hidden)* | *(invisible)* |
| Connect | *(merged into resolve)* | *(invisible)* |
| Scout / Sync (opponent) | Sync Stats | *(invisible)* |
| Tracked (badge) | Opponent | Opponent |
| "hasn't been linked to a GameChanger team yet" | N/A | "Scouting stats aren't available for this team" |
| "after the next scouting sync" | N/A | "Stats are on their way. Check back soon." |

Filter pills on admin opponents page: "All" | "Stats loaded" | "Needs linking" | "Hidden"

Per-row status badges in admin opponents table (replaces current Resolved/Unresolved/Hidden badges):
- "Needs linking" (`bg-orange-100 text-orange-800`)
- "Syncing..." (`bg-yellow-100 text-yellow-800`)
- "Stats loaded" (`bg-green-100 text-green-800`)
- "Sync failed" (`bg-red-100 text-red-800`)
- "Hidden" (`bg-gray-100 text-gray-600`)

### TN-6: Data Repair Logic

The repair command propagates existing `opponent_links` resolutions that were never written through:

1. Query all `opponent_links` rows where `resolved_team_id IS NOT NULL`
2. For each: upsert `team_opponents(our_team_id, resolved_team_id)` and set `teams.is_active = 1`
3. When replacing a stub with a resolved team, reassign all FK references from the stub to the resolved team (consistent with TN-1 step 4)
4. Report counts: how many `team_opponents` rows created/updated, how many teams activated, how many game rows reassigned
5. Idempotent: safe to run multiple times

## Open Questions
None -- all resolved during discovery.

## History
- 2026-03-28: Created as E-172. All four expert consultations completed (coach, DE, SE, UXD). Coach walkthrough of 7 templates completed. Absorbs E-171-resolve-search-enrichment scope. E-171 abandoned and archived.
- 2026-03-28: Three internal review iterations + Codex spec review completed. 72 total findings (52 accepted, 20 dismissed).
- 2026-03-28: Renumbered to E-173 (E-172 reassigned to Standalone Scouting Report Generator before commit).
- 2026-03-28: Set to READY.

## Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 12 | 7 | 5 |
| Internal iteration 1 -- PM holistic | 7 | 7 | 0 |
| Internal iteration 1 -- UXD holistic | 7 | 3 | 4 |
| Internal iteration 1 -- DE holistic | 1 | 1 | 0 |
| Internal iteration 1 -- Coach holistic | 10 | 9 | 1 |
| Internal iteration 1 -- SE holistic | 3 | 3 | 0 |
| Internal iteration 2 -- CR spec audit | 8 | 3 | 5 |
| Internal iteration 2 -- PM holistic | 7 | 7 | 0 |
| Internal iteration 2 -- DE holistic | 4 | 2 | 2 |
| Internal iteration 2 -- SE holistic | 7 | 4 | 3 |
| Internal iteration 3 -- CR spec audit | 2 | 2 | 0 |
| Internal iteration 3 -- DE holistic | 0 | 0 | 0 |
| Internal iteration 3 -- SE holistic | 0 | 0 | 0 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **72** | **52** | **20** |
