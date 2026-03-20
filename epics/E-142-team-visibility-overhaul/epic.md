# E-142: Team Visibility Overhaul -- Fix Invisible Teams After Add

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview

Newly added teams are invisible in the dashboard due to three independent data-dependency gaps: missing `user_team_access` rows on team creation, `get_team_year_map()` omitting teams without stat data, and the opponent list ignoring `team_opponents` entries with no game data. This epic fixes all three bugs and adds empty-state UX so teams and opponents are visible immediately after being added, before any data is crawled.

## Background & Context

Jason reported that team 954 (Standing Bear Freshman Grizzlies 2026) was added via the admin UI as a member team, with `user_team_access` correctly linking user 1 to team 954, but the dashboard at `/dashboard?year=2026` doesn't show it. The root cause: `get_team_year_map()` only returns teams with rows in `player_season_batting` or `player_season_pitching`. Additionally, Jason noted general friction with team management ("I can't ever get it to work"), and opponents also don't appear until game data exists.

**Expert consultation (2026-03-20):**
- **Coach**: Teams MUST be visible immediately after add. Opponents MUST appear when linked. Empty state should feel "ready and waiting," not broken.
- **SE**: Confirmed 3 independent bugs, all fixable without schema changes. Core fixes touch `db.py` and `admin.py`; UX polish extends to `dashboard.py` and templates.
- **DE**: Agrees no schema changes needed. Calendar year fallback is correct (not `created_at`). Optional `season_id` FK on `team_opponents` deferred.
- **UXD**: Yellow info card for empty state, muted pill styling for no-data teams, always include current year in dropdown, enhanced post-add flash.

## Goals
- Newly added member teams appear in the dashboard immediately after creation, with no data crawl required
- The year selector includes the current year whenever active teams exist, even if no stat data is loaded
- Linked opponents appear on `/dashboard/opponents` immediately after being linked, before any games are crawled
- Empty states communicate status clearly with coaching-appropriate messaging

## Non-Goals
- Schema changes (no migrations required; fixes are query-layer, route-layer, and template-layer)
- Roster display in the empty state (separate future feature)
- Prior-season scouting data surfacing for opponents (future idea)
- Scheduled-game indicators before games are played (future idea)
- `season_id` FK addition to `team_opponents` (deferred optimization)

## Success Criteria
- A team added via `/admin/teams` with `membership_type=member` is visible in the dashboard on the next page load, with no crawl, no logout/login, and no container rebuild required
- A team added with no stat data shows a clear empty-state message on the Batting, Pitching, and Games dashboard tabs; the Opponents tab shows linked opponents or the empty-state message if none are linked
- Opponents linked via `team_opponents` appear in the opponent list even when no games exist for them
- The year selector includes the current calendar year when any active team exists, regardless of stat data (as a dropdown when multiple years exist, or a static label when only one year exists)
- All existing dashboard functionality continues working unchanged for teams with stat data

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-142-01 | Access fan-out on member team create | TODO | None | - |
| E-142-02 | Year map fallback for no-data teams | TODO | None | - |
| E-142-04 | Opponent list fallback to team_opponents | TODO | E-142-02 | - |
| E-142-03 | Dashboard empty state UI | TODO | E-142-02, E-142-04 | - |
| E-142-05 | Post-add flash with next-step hint | TODO | E-142-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Year Map Fallback Strategy

`get_team_year_map()` currently returns `team_id → year` by querying `player_season_batting` and `player_season_pitching` UNIONed and JOINed to `seasons.year`. The fix adds a post-query fallback: for each `team_id` in the input list that is NOT in the query result, map it to the current calendar year. This avoids schema changes and handles the common case (team added during the current season). The edge case of a team added in December for a spring season is low-consequence and self-correcting once data is loaded.

**has_stat_data signal**: After the fallback, every team is in `team_year_map`, so "team is in map" can no longer distinguish teams with real stat data from fallback teams. E-142-02 must also produce a `get_teams_with_stat_data(team_ids: list[int]) → set[int]` function that returns only the team ids with actual rows in the stat tables. E-142-03 consumes this to drive `has_stat_data` per team.

### TN-2: user_team_access Fan-Out

When a team is created with `membership_type='member'`, the system must also insert `user_team_access` rows for all existing users. This mirrors the logic in `_assign_member_teams()` in `auth.py`, but triggered at team creation time rather than session creation. The `_insert_team_new()` function must return the new team's `id` (via `lastrowid`) so the fan-out can reference it. The fan-out uses `INSERT OR IGNORE` to be idempotent.

No session invalidation is needed: `_get_permitted_teams()` is called on every request from `user_team_access`, so the new row is picked up on the next page load automatically.

### TN-3: Opponent List UNION Strategy

`get_team_opponents()` must be extended to include opponents from `team_opponents` that have no rows in `games`. The approach: after the existing games-based query, UNION in `team_opponents` entries (filtered by the active team and current year via `first_seen_year`) that are NOT already in the games result. For these no-game opponents, the **data layer** returns `games_played=0`, `wins=0`, `losses=0`, and NULL for date columns. The **template layer** renders `games_played=0` as `--` (not "0" or "0-0") to avoid implying the team played zero games -- it means "no data," not "zero games played."

The `first_seen_year` (INTEGER) vs `season_id` (TEXT) impedance mismatch: extract year from `season_id` parameter (first 4 characters) for comparison with `first_seen_year`. This is a pragmatic workaround; a clean `season_id` FK on `team_opponents` is deferred.

### TN-4: Empty State Design

When a team has no stat data, the dashboard shows:
- **Team pill**: Muted styling (gray tones instead of blue) to signal pending state. The `_team_selector.html` partial needs a `has_stat_data` boolean per team entry. The `has_stat_data` flag is sourced from `get_teams_with_stat_data()` (produced by E-142-02), NOT from `team_year_map` membership (which includes fallback teams after E-142-02).
- **Content area**: Yellow info card (`bg-yellow-50 border-yellow-200`) with message: "No stats loaded for [year] yet. Stats will appear after your admin runs a data sync for this team." This card appears on the Batting, Pitching, and Games tabs.
- **Opponent tab**: If the team has linked opponents via `team_opponents` (from E-142-04) but no stat data, show the opponent list (not the generic empty card). The generic empty card only shows on the Opponents tab when there are zero linked opponents AND zero game-based opponents.
- **Year selector**: The `_team_selector.html` macro currently hides the year dropdown when `available_years|length <= 1`. When no-data teams cause the current year to be the only year, the dropdown should still render so the user understands the year context. Adjust the `_multi_year` conditional to always show the year label when only one year exists (even without the dropdown).

### TN-5: Post-Add Flash Enhancement

The success flash after team creation must include a next-step hint with the `bb data sync` command. **Security constraint**: the `teams.html` template renders `{{ msg }}` with Jinja2 autoescaping enabled, and `msg` comes from a query parameter. Using `| safe` is prohibited per `.claude/rules/jinja-safety.md`. HTML in the query string would be escaped to `&lt;code&gt;`.

**Approach**: Replace the current `?msg=Team added: {name}` redirect with `?added=1&team_name={name}` (do NOT pass both -- the existing `msg` block renders unconditionally and would produce a duplicate banner). The `teams.html` template checks for `added` and renders the enhanced flash with the `bb data sync` command hint as server-controlled static markup -- no `| safe` needed because the `<code>` tags are in the template, not in the query string. The team name is rendered with normal autoescaping. The flash remains dismissible via page navigation (no JS).

## Open Questions
- None blocking. Deferred items captured in Non-Goals.

## History
- 2026-03-20: Created. Discovery complete with input from coach, SE, DE, UXD. All experts agree: no schema changes needed.
- 2026-03-20: Spec review iteration 1 (6 findings, all accepted). Refinement: added `get_teams_with_stat_data()` to E-142-02; fixed AC-2 tabs scope; fixed opponent data/display layer separation; rewrote E-142-05 for flash safety; fixed all dependency fields.
- 2026-03-20: Spec review iteration 2 (3 findings, all accepted). Tightened duplicate banner prevention; updated stale scope narrative; made AC-4 concrete.
- 2026-03-20: Spec review iteration 3 (5 findings, all accepted). Year-scoped AC-7 to E-142-04 result; normalized year selector contract (dropdown vs label); fixed "No games yet" → `--` in E-142-04 description; added test files to E-142-03 and E-142-05 file lists.
