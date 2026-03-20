# E-133: Year Selector Dropdown

## Status
`COMPLETED`

## Overview
Add a year selector dropdown to all dashboard pages so coaches can view past seasons' data. In GameChanger, a "team" IS a team-for-a-season -- "Top Dogg 14U" for 2025 summer is a separate GC team entity from "Top Dogg 14U" for 2026 summer. The year dropdown filters which teams appear in the team selector, defaulting to the current year (used 97% of the time). This replaces the current season pill-button selector with a compact, unobtrusive dropdown.

## Background & Context
E-127 revealed a fundamental misunderstanding: our season selector assumed one team might span multiple seasons. In reality, each GC team entity has a fixed `season_year` (confirmed by API Scout -- it's a first-class field on every GC team object). The current `_season_selector.html` renders pill buttons for each `season_id` found in stat tables, but since a GC team only ever has one season, this selector is conceptually wrong. The correct UX is: pick a year (which determines which team entities are visible), then pick a team within that year.

**Expert consultation completed (2026-03-19)**:
- **API Scout**: Confirmed `season_year` INTEGER and `season_name` TEXT are top-level fields on every GC team object. One GC team = one season is the GC data model.
- **DE**: No migration needed for dashboard. Year can be derived from existing `seasons.year` column via join to stat tables. Migration only needed later if admin team list needs year filtering (teams with no stat data). Recommended `get_available_years` DB function using `seasons` join (not string parsing).
- **SE**: Confirmed approach is modest scope. Key insight: the DB function must work across ALL permitted teams (not per-team) to build the year→teams mapping. Recommended `get_team_year_map(team_ids)` returning `team_id → year` mapping. Noted: teams with no stats won't appear in year filter (acceptable).
- **UXD**: Year dropdown should go right-aligned in the team selector row (not navbar). Native `<select>`, hidden when only 1 year. Replace season selector entirely. Year form submission should NOT carry `team_id` -- let route default to first team for new year.

No expert consultation required for coaching domain -- this is a pure UI/data-plumbing feature.

## Goals
- Coaches can view any past year's stats by selecting a year from a dropdown
- Current year is the default -- coaches never need to interact with the dropdown for current-season work
- The dropdown is compact and unobtrusive (not "in your face")
- Year selection persists across page navigation (batting -> pitching -> games -> opponents)

## Non-Goals
- Spring/summer distinction within a year (deferred -- just year for now)
- Cross-season player tracking or player identity across years
- Adding `season_year` column to teams table (no migration -- derive from existing data)
- Modifying the crawler/loader to populate year data
- Admin UI changes for year management

## Success Criteria
- Dashboard pages show a year dropdown defaulting to the current year
- Selecting a past year filters the team selector to show only teams with data in that year
- Stat pages (batting, pitching, games, opponents) display data for the correct year
- Year selection propagates through ALL internal links (bottom nav, team pills, game/opponent/player links, back-links)
- Existing bookmarks with `?team_id=N` (no year param) continue to work correctly
- The dropdown is visually compact and does not dominate the page header area

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-133-01 | Year dropdown UI and route integration | DONE | None | - |
| E-133-02 | Remove legacy season selector | DONE | E-133-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Year Derivation (No Migration)
Year is derived from existing data, not a new column. One new DB function is needed:

**`get_team_year_map(team_ids: list[int]) -> dict[int, int]`**: For a list of team IDs, returns a mapping of `team_id → year` by querying stat tables joined to `seasons.year`. This powers the year dropdown and team filtering.

```sql
SELECT DISTINCT t.team_id, s.year
FROM (
    SELECT team_id, season_id FROM player_season_batting WHERE team_id IN (...)
    UNION
    SELECT team_id, season_id FROM player_season_pitching WHERE team_id IN (...)
) t
JOIN seasons s ON s.season_id = t.season_id
```

The available years list is derived from this map in Python: `sorted(set(map.values()), reverse=True)`. This is not a separate DB function.

Teams with no stat data won't appear in the year filter. This is acceptable -- a team with no data has nothing to display.

### TN-2: Year Filtering Approach and Parameter Resolution

The `year` query parameter is added to all dashboard routes. It propagates through the bottom nav bar and all internal links, just like `team_id` and `season_id` do today.

**Parameter resolution order** (critical for backward compat):

1. Build `team_year_map` for ALL `permitted_teams` (unfiltered).
2. If `team_id` is present and in `permitted_teams`: **team_id wins**. Derive year from `team_year_map[team_id]`. The year dropdown reflects this derived year. This preserves backward compatibility with existing bookmarks and links that carry `team_id` without `year`.
3. If `team_id` is absent: use `year` param (or default) to filter `permitted_teams` by year. Pick the first team in the filtered list.
4. **Default year** (no `year` param and no `team_id` param): use current calendar year. If no teams have data for the current year, fall back to the most recent year with data.
5. **Invalid `year` param** (explicit `year` with no matching teams, e.g., manual URL `?year=2020`): fall back to the most recent year with data.

After resolving the active team, derive `season_id` from its available seasons (existing `get_available_seasons()`).

**Year ↔ team_id interaction in the UI**: The year dropdown submits `?year=YYYY` only (no `team_id`), so changing year always triggers resolution path 3. Team pill links carry both `team_id` and `year`, so clicking a team triggers resolution path 2. This means `team_id` always wins when present, and year-only submissions always pick the first team in that year.

### TN-3: UI Placement and Design
The year dropdown renders as a native `<select>` element **right-aligned within the team selector row**:

```
[Varsity] [JV] [Freshman] ................ Year: [2026 ▾]
```

- Uses `justify-between` on the flex container (team pills left, year select right)
- Label "Year:" in `text-xs text-gray-500` (visually subordinate)
- Select styled: `text-sm border border-gray-300 rounded px-2 py-1 bg-white`
- No JavaScript framework: a minimal inline `onchange="this.form.submit()"` handler triggers form submission
- Hidden when only one year has data (same pattern as existing selectors)
- On mobile, native OS picker handles touch targets; flex wraps naturally

### TN-4: Year-to-Season Resolution
Since a GC team has exactly one season, selecting a year + team implicitly selects a season. The route derives `season_id` from the team's data rather than requiring it as a separate parameter. The `season_id` query param remains supported for backward compatibility but the year dropdown is the primary navigation mechanism.

### TN-5: Link Propagation
The `year` parameter must propagate through ALL internal links, not just the bottom nav bar. Specific surfaces:
- **Bottom nav bar** (`base.html`): Batting/Pitching/Games/Opponents links
- **Team selector pills** (`_team_selector.html`): Each team pill link must carry `year`
- **Game list rows**: Links from game list → game detail page
- **Opponent list rows**: Links from opponent list → opponent detail page
- **Player name links**: Links from stat tables → player profile page
- **Back-links**: Player profile and game detail pages linking back to list pages

Any internal `<a href>` that currently carries `team_id` and/or `season_id` must also carry `year`. The pattern is the same as the existing query string propagation for `team_id`/`season_id`.

### TN-6: No Past-Year Warning Banner
The current `is_current_season` warning banner ("Showing X data -- no Y season data...") is removed entirely when the legacy season selector is removed (E-133-02). The year dropdown makes past-year viewing an explicit user choice, so no warning is needed. If the user selects 2025, they chose it deliberately.

## Open Questions
None -- all questions resolved during consultation.

## History
- 2026-03-19: Created. Expert consultation with SE, DE, UXD, API Scout completed.
- 2026-03-19: Revised after full consultation synthesis. Removed migration story (DE: derive year from existing `seasons.year` join). Moved year dropdown from navbar to team selector row (UXD). Simplified from 3 stories to 2. Set to READY.
- 2026-03-19: Codex spec review triage. P1 link propagation: refined -- added TN-5, expanded AC-6/AC-7/file list to cover all internal links. P2 TN-1 stale text: fixed -- clarified one function + derivation. P2 AC-3 ambiguity: fixed -- concrete decision to remove banner (TN-6). P2 missing tests: fixed -- added tests/ to E-133-02 file list.
- 2026-03-19: Fresh refinement pass. Found backward-compat issue: old bookmarks with `?team_id=N` would break if year filtering runs first. Rewrote TN-2 with explicit parameter resolution order (team_id wins when present, year filters when team_id absent). Updated AC-2/AC-3 to match. Refined AC-7 (detail pages pass year through for links, don't filter by year). Fixed TN-3 JS terminology. Added backward-compat to Success Criteria.
- 2026-03-20: COMPLETED. Both stories implemented, reviewed (codex review: 3 findings fixed; integration CR: 1 finding fixed), and verified. Year dropdown added to all dashboard pages with full parameter resolution (TN-2), link propagation across all surfaces (TN-5), and backward compatibility for existing bookmarks. Legacy season selector removed; year dropdown is the sole time-navigation mechanism. 275 tests passing.

  **Documentation assessment**: Trigger 1 fires (new feature ships -- year selector dropdown changes how coaches navigate between seasons). Trigger 5 fires (changes how users interact with the dashboard). Recommend dispatching docs-writer to update `docs/coaching/` with year dropdown usage if coaching docs exist, and `docs/admin/` if dashboard admin docs reference the season selector.

  **Context-layer assessment**:
  1. New convention/pattern: **No** -- year param propagation follows existing query string patterns.
  2. Architectural decision: **No** -- year derived from existing `seasons.year` join; no new infrastructure.
  3. Footgun/boundary: **No** -- parameter resolution order (TN-2) is well-documented in code comments.
  4. Agent behavior/routing: **No** -- no changes to agent dispatch or coordination.
  5. Domain knowledge: **No** -- "one GC team = one season" is already documented in CLAUDE.md data model section.
  6. New CLI/workflow: **No** -- no new commands or workflows.
  Context-layer verdict: All six triggers **No**. No context-layer codification needed.

  **Ideas backlog review**: No CANDIDATE ideas are directly unblocked by E-133. The year dropdown is UI-only and does not add data capabilities that would unblock data-layer ideas.

  **Vision signals**: 22 unprocessed signals exist in `docs/vision-signals.md`. No new signals from this epic. User may want to "curate the vision" at a convenient pause point.
