# E-153: Team-Centric Coaching Dashboard

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Rebuild the coaching dashboard around the coach's mental model: "I'm coaching my team -> show me my schedule -> let me scout my opponents." The current dashboard leads with batting stats and has no schedule view. This epic makes the schedule the primary landing page, merges the Games and Opponents tabs into it, redesigns the opponent detail page to lead with pitching, and handles graceful empty states for unlinked and unscouted opponents. A prerequisite schedule loader populates upcoming games into the database so coaches see their full season -- not just past results.

## Background & Context
The user (Jason, system operator and SB Freshman coach) identified the core gap: "The entire point of this is that I run a team. And I can see my future opponents so that I can scout them." The current dashboard has four bottom-nav tabs (Batting, Pitching, Games, Opponents) that don't match the coaching workflow. The Games tab shows only completed games. The Opponents tab is a flat list disconnected from the schedule. There is no way to see upcoming games or click through to scout a future opponent.

**Expert consultation completed:**
- **Baseball Coach**: Schedule must be the landing page. Upcoming games need days-until countdown and scouted indicator. Opponent detail must lead with pitching ("Who's on the mound?"). Pre-game clicks go to opponent scouting; post-game clicks go to box score review. Season aggregates are genuinely useful for pregame prep with game count alongside every stat. Own-team stats should be one click away, not the default landing.
- **UX Designer**: 3-tab navigation (Schedule | Batting | Pitching) replaces the current 4-tab nav. Games and Opponents merge into Schedule. Upcoming games get visual distinction (tinted rows, NEXT badge). Opponent detail sections reorder: pitching card -> batting tendencies -> last meeting -> full tables. Unlinked opponents get a yellow info card with admin shortcut. Admin cleanup is a separate epic. Manual opponent linking stays admin-only.
- **Software Engineer**: The `games` table only contains completed games -- `_upsert_game()` hardcodes `status='completed'`. A schedule loader reading `schedule.json` is a hard prerequisite. The `get_team_opponents()` query already has dead `next_game_date` logic that will activate once scheduled games exist. Query adaptation is straightforward. Recommended a new `schedule.py` routes file.
- **Data Engineer**: Confirmed the schedule data gap. No new indexes needed for scouting-status queries. Recommended a CTE approach for `has_stats` badge. `get_team_games()` needs `g.status` added to its SELECT list. The `opponent_links` -> `team_opponents` bridge gap means E-152-seeded name-only opponents may not appear in dashboard queries until OpponentResolver runs.

## Goals
- Coaches land on their team's schedule showing upcoming AND past games
- Each schedule row links to opponent scouting (upcoming) or box score (completed)
- The opponent scouting report leads with pitching and handles unlinked/unscouted states gracefully
- Navigation matches the coaching mental model (3 tabs: Schedule, Batting, Pitching)
- Upcoming game data is loaded into the database from already-crawled schedule.json files

## Non-Goals
- Admin UI cleanup (Teams page, Opponents tab confusion) -- separate epic
- Coach self-service opponent linking -- admin-only in this epic
- Proactive flags and alerts (short rest, pitch count, streaks) -- requires per-game stat pipeline
- PDF/printable scouting report export
- LLM-powered chat agent
- Per-game opponent stats (already available for scouted teams; not adding new stat compilation)
- New database migrations or schema changes (the `games.status` column already supports 'scheduled')

## Success Criteria
- A coach logging in lands on their schedule view showing upcoming and past games in chronological order
- Upcoming games display days-until, opponent name, home/away, and a scouted/unscouted indicator
- Completed games display score, W/L, opponent name, and link to box score
- Clicking an opponent name from any schedule row opens the opponent scouting detail
- The opponent detail page shows pitching stats first, then batting, with clean empty states for unlinked and unscouted opponents
- Bottom navigation has exactly 3 tabs: Schedule (active on landing), Batting, Pitching
- The schedule is populated automatically when `bb data sync` runs (schedule loader wired into pipeline)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-153-01 | UX design spec for coaching dashboard | DONE | None | - |
| E-153-02 | Schedule loader | DONE | None | - |
| E-153-03 | Schedule landing page and navigation restructure | DONE | E-153-01, E-153-02 | - |
| E-153-04 | Opponent detail redesign | DONE | E-153-01, E-153-03 | - |

## Dispatch Team
- ux-designer
- software-engineer

## Technical Notes

### TN-1: Schedule Data Flow
The `ScheduleCrawler` already writes `schedule.json` during member sync. The missing piece is loading that data into the `games` table. The schedule loader (E-153-02) reads `schedule.json` and upserts game rows with `status='scheduled'`. When the game completes and the boxscore is loaded, `_upsert_game()` overwrites the row with `status='completed'` and actual scores -- the existing upsert uses `ON CONFLICT(game_id) DO UPDATE`, so scheduled rows are naturally upgraded.

Schedule events have `pregame_data.opponent_id` (a `root_team_id`, NOT a canonical UUID), `opponent_name`, and `pregame_data.home_away` (values: `"home"`, `"away"`, or `null`). The loader must resolve opponent team IDs via `opponent_links.resolved_team_id` (for linked opponents) or ensure a stub `teams` row exists (for name-only opponents). After E-152, `opponent_links` is populated for all schedule opponents.

**Season ID resolution**: The schedule loader must assign a `season_id` to each game row. Use `config.season` -- the same season_id value passed to all other loaders in the pipeline (see `src/pipeline/load.py` line 83 where `GameLoader` receives `config.season`). This is the single authoritative source for season_id during a sync run.

**Filtering**: Schedule events include non-game entries (practices, events) and canceled games. The loader must filter to actual games only (check `event_type` or equivalent field in schedule.json) and skip canceled events (check `status` or `is_canceled` fields). Consult the endpoint documentation at `docs/api/endpoints/get-teams-team_id-schedule.md` for the exact field names and values.

### TN-2: Opponent Resolution Chain for Schedule Games
Each schedule event contains an opponent reference. The resolution path is:
1. Look up `opponent_links` by `our_team_id` + `root_team_id` (from `pregame_data.opponent_id`)
2. If `resolved_team_id IS NOT NULL` -> use that as the game's opponent `teams(id)`
3. If `resolved_team_id IS NULL` (name-only) -> find an existing `teams` row by name match, or create a stub `teams` row (`membership_type='tracked'`, `source='schedule'`)
4. Insert the game row referencing both team IDs

**Home/away determination**: Use `pregame_data.home_away` from `schedule.json`. Values are `"home"` (our team is home), `"away"` (our team is away), or `null` (unknown -- e.g., tournament games). When `home_away` is null, assign our team as `home_team_id` and opponent as `away_team_id` as a convention. The dashboard template should handle the null-home_away case gracefully (show "TBD" or omit the H/A indicator rather than displaying incorrect information).

**Stub teams**: When creating a stub `teams` row for a name-only opponent, set `source='schedule'` to distinguish from teams created via other paths (e.g., `source='gamechanger'` for API-resolved teams). This is informational only -- no behavioral difference.

The schedule loader upserts a `team_opponents` junction row for each opponent discovered from the schedule (ON CONFLICT DO NOTHING), ensuring the opponent appears in `get_team_opponents()` dashboard queries regardless of whether OpponentResolver has run. The `first_seen_year` column must be populated -- derive it as `int(season_id[:4])` to match the extraction pattern used by `get_team_opponents()` (which filters `first_seen_year = CAST(substr(:season_id, 1, 4) AS INTEGER)`). Without `first_seen_year`, the opponent will not appear in the junction fallback query.

### TN-3: Schedule View Query Design
The schedule view query extends `get_team_games()` with:
- `g.status` added to SELECT (to distinguish completed/scheduled)
- `ORDER BY g.game_date ASC` (chronological)
- LEFT JOIN to determine scouting status per opponent (CTE on `player_season_batting` UNION `player_season_pitching` for `has_stats`)

DE-recommended CTE approach for scouting status:
```sql
WITH opp_has_stats AS (
    SELECT DISTINCT team_id FROM player_season_batting WHERE season_id = :season_id
    UNION
    SELECT DISTINCT team_id FROM player_season_pitching WHERE season_id = :season_id
)
```
This checks batting OR pitching rows, consistent with the opponent detail page's "full stats" definition (TN-6). A team with only pitching data (no batting rows) is still considered scouted.
No new indexes needed -- existing `idx_psb_team_season`, `idx_games_season_id`, `idx_games_home_team_id`, `idx_games_away_team_id` are sufficient.

### TN-4: Navigation Structure
Current: `Batting | Pitching | Games | Opponents` (4 tabs)
New: `Schedule | Batting | Pitching` (3 tabs)

- Schedule replaces `/dashboard/` as the root landing page
- Batting moves to `/dashboard/batting` (current `/dashboard/` URL)
- Pitching stays at `/dashboard/pitching`
- Old `/dashboard/games` and `/dashboard/opponents` routes continue to work (existing pages still accessible via direct URL and internal links) but are removed from the bottom nav
- `active_nav` values: `'schedule'`, `'batting'`, `'pitching'`

### TN-5: Schedule Row Behavior
Each game row links differently based on status:
- **Upcoming game**: opponent name links to `/dashboard/opponents/{opponent_team_id}` (scouting report)
- **Completed game**: opponent name links to `/dashboard/opponents/{opponent_team_id}` (scouting report); score links to `/dashboard/games/{game_id}` (box score)

Row content per status:
- **Upcoming**: date, days-until badge, opponent name, home/away, scouted indicator (badge showing whether opponent has stats data)
- **Completed**: date, opponent name, home/away, score, W/L indicator

The nearest upcoming game gets a visual emphasis treatment (e.g., "NEXT" badge or bolder styling). "Nearest upcoming" is defined as the game with `MIN(game_date) WHERE game_date >= date('now') AND status = 'scheduled'`.

**Opponent record on schedule rows** (SHOULD HAVE): If opponent record data is available (from `games` table W-L aggregation), display it in a compact format (e.g., "(8-2)") next to the opponent name. This gives coaches a quick threat signal without clicking through.

### TN-6: Opponent Detail Page Sections (Redesigned Order)
1. **Header**: Opponent name + season record (W-L) + game count
2. **Pitching card** (promoted from bottom): Top 3 pitchers by innings pitched (most usage = most likely to face), displaying ERA, K/9, BB/9, K/BB ratio, and games pitched. If `players.throws` is populated for a pitcher, display handedness (L/R). If pitch count data available, show recent usage.
3. **Team batting summary**: Team-level OBP, K%, BB%, SLG -- tendencies that affect game planning (not full table). Computed as aggregates across all batters in the season. Display the total number of games the team has played alongside these rates (e.g., "Team Batting (12 games)").
4. **Last Meeting card**: Most recent head-to-head game result (existing)
5. **Full pitching table**: Sortable, all pitchers (existing, repositioned)
6. **Full batting table**: Sortable, all batters (existing, repositioned)

**Empty state detection** (three mutually exclusive states):
- **Unlinked opponent**: The opponent `teams(id)` has no row in `opponent_links` with `resolved_team_id IS NOT NULL` for the current user's team context, AND the opponent `teams` row has `public_id IS NULL`, AND `player_season_batting`/`player_season_pitching` have no rows for this team_id + season_id. Yellow info card: "Stats not available. This opponent hasn't been linked to a GameChanger team yet." Admin users see "Link this team in Admin ->" shortcut. The admin shortcut links to `/admin/opponents/{link_id}/connect` if an `opponent_links` row exists, or `/admin/opponents` (general opponents page) if none exists.
- **Linked but unscouted**: The opponent has a corresponding `opponent_links` row with `resolved_team_id IS NOT NULL` for the active member team's `our_team_id`, OR the opponent `teams` row has `public_id IS NOT NULL`, BUT `player_season_batting`/`player_season_pitching` have no rows for this team_id + season_id. Yellow info card: "This team is linked but stats haven't been loaded yet."
- **Full stats**: `player_season_batting` or `player_season_pitching` has at least one row for this team_id + season_id. All sections render with data. No yellow info cards.

**Admin role detection**: `request.state.user` does NOT contain the user's role directly. The route handler must query the database for the user's role (via `users` table) or check `ADMIN_EMAIL` env var match to determine admin status. Consult the existing `_require_admin()` pattern in `src/api/routes/admin.py` for the admin detection logic.

### TN-7: Game Count Transparency
Per coach consultation, every stat display must show the sample size. "ERA 2.10 (8 GP)" is more honest than "ERA 2.10" alone. The `games` column (returned as `games` in the query result -- NOT aliased as `gp`) is already returned by both batting and pitching scouting queries in `db.py` -- templates must render it alongside rate stats, not just as a sortable column. This applies to the pitching card (per-pitcher GP), the team batting summary (team game count), and the full stat tables.

### TN-8: Dependency on E-152
This epic depends on E-152 (Schedule-Based Opponent Discovery) being deployed before E-153-02 can produce correct results at runtime. E-152 populates `opponent_links` from schedule.json and wires OpponentResolver into the sync pipeline. Without E-152's data, the schedule loader's opponent resolution chain (TN-2) has no `opponent_links` rows to query. E-152 is currently READY (not yet dispatched) -- it is a runtime dependency, not a code dependency. E-153 code can be written and tested independently.

## Open Questions
- None -- all questions resolved during expert consultation.

## History
- 2026-03-24: Created. Expert consultation with baseball-coach, ux-designer, software-engineer, data-engineer.
- 2026-03-24: Dispatch completed. 4 stories implemented (UXD: E-153-01, SE: E-153-02/03/04). Per-story CR: E-153-01 skipped (context-layer-only); E-153-02 APPROVED round 2 (1 MUST FIX fixed); E-153-03 APPROVED round 1 (1 SHOULD FIX dismissed); E-153-04 APPROVED round 2 (4 MUST FIX fixed, 1 SHOULD FIX fixed). CR integration review: APPROVED (1 SHOULD FIX fixed -- game_detail active_nav, 1 dismissed). Codex code review: 4 findings, all dismissed (pre-existing architecture, schema constraint, domain inapplicable). Epic COMPLETED.

### Dispatch Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-153-01 | 0 | 0 | 0 |
| Per-story CR -- E-153-02 | 1 | 1 | 0 |
| Per-story CR -- E-153-03 | 1 | 0 | 1 |
| Per-story CR -- E-153-04 | 5 | 5 | 0 |
| CR integration review | 2 | 1 | 1 |
| Codex code review | 4 | 0 | 4 |
| **Total** | **13** | **7** | **6** |

### Documentation Assessment
Triggers fired: (1) New feature shipped -- schedule landing page, 3-tab navigation, opponent detail redesign; (5) Epic changes how users interact with the system -- `/dashboard/` now serves schedule instead of batting, navigation restructured from 4 tabs to 3. `docs/coaching/scouting-reports.md` describes a "Coming Soon" scouting report feature that is now partially live -- needs updating to reflect the current dashboard layout, schedule-first workflow, and opponent detail page structure. **Action required**: dispatch docs-writer to update `docs/coaching/scouting-reports.md`.

### Context-Layer Assessment
1. **New convention, pattern, or constraint?** No. Schedule loader follows the existing loader pattern (added to `_LOADERS` list). No new conventions established.
2. **Architectural decision with ongoing implications?** No. The URL restructuring (`/dashboard/` → schedule, `/dashboard/batting` → batting) is an app-level routing change, not an architectural decision that affects future epic planning.
3. **Footgun, failure mode, or boundary discovered?** No. The `_check_opponent_authorization` pattern (games-table-based auth for stub opponents) follows existing patterns. No new gotchas discovered.
4. **Change to agent behavior, routing, or coordination?** No. No agent definitions, rules, skills, or hooks were modified.
5. **Domain knowledge discovered?** No. All domain insights (pitching-first, schedule-as-landing, 3-tab nav) were captured during E-153 planning and already reflected in the UX design spec. No new domain discoveries during implementation.
6. **New CLI command, workflow, or operational procedure?** No. No new `bb` commands or scripts added. The schedule loader runs automatically as part of the existing sync pipeline.

All context-layer triggers: **No**. No claude-architect dispatch required.

### Ideas Backlog Review
- **IDEA-035 (Opponent Page Redesign)**: E-153-04 delivered the opponent detail redesign (pitching-first, empty states, team batting summary). IDEA-035 scope ("rate stats, flags, PDF export") is partially addressed -- rate stats done, proactive flags and PDF export remain. Recommend updating IDEA-035 to reflect reduced scope (flags + PDF only).
- **IDEA-037 (Scouting Report Redesign)**: Overlaps with E-153-04. Rate stats and pitching-first are done. Remaining scope: proactive flags, PDF export, further enhancements. Recommend updating to note E-153 partial delivery.
- Other CANDIDATEs: No additional ideas unblocked by E-153.

### Vision Signals
10+ unprocessed signals exist in `docs/vision-signals.md`. Advisory: consider "curate the vision" when convenient. This does not block archival.

- 2026-03-24: Epic set to ACTIVE. Dispatch started.
- 2026-03-24: READY. 7 review passes, 47 total findings (45 accepted, 2 dismissed). Review scorecard:

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 8 | 0 |
| Internal iteration 1 -- Holistic (SE+DE+Coach+UXD) | 19 | 19 | 0 |
| Internal iteration 2 -- CR spec audit | 6 | 6 | 0 |
| Internal iteration 2 -- Holistic (SE+DE+Coach+UXD) | 0 | 0 | 0 |
| Codex iteration 1 | 9 | 7 | 2 |
| CR iteration 3 (post-Codex) | 1 | 1 | 0 |
| Codex iteration 2 | 4 | 4 | 0 |
| **Total** | **47** | **45** | **2** |

Dismissed: P2-6 (SE routing correct for loader code, no schema changes), P2-7 (endpoint doc exists, no api-scout consultation needed).
