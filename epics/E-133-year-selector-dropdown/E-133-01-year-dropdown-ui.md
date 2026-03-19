# E-133-01: Year Dropdown UI and Route Integration

## Epic
[E-133: Year Selector Dropdown](epic.md)

## Status
`TODO`

## Description
After this story is complete, all four main dashboard pages will display a compact year dropdown in the team selector row. Selecting a year filters the team selector to show only teams from that year. The current calendar year is the default. Year selection persists across page navigation via query parameter propagation. A new DB function provides the team-to-year mapping that powers the dropdown and filtering.

## Context
The current season selector (`_season_selector.html`) renders pill buttons per season_id, but since each GC team entity has exactly one season, it's conceptually wrong. This story replaces the primary time-navigation mechanism with a year dropdown. The legacy season selector is left in place during this story (E-133-02 removes it) to minimize risk.

## Acceptance Criteria
- [ ] **AC-1**: A new function in `src/api/db.py` accepts a list of team IDs and returns a mapping of `team_id → year` by joining stat tables to `seasons.year`, per epic Technical Notes TN-1.
- [ ] **AC-2**: All four main dashboard routes (`/dashboard`, `/dashboard/pitching`, `/dashboard/games`, `/dashboard/opponents`) accept a `year` query parameter. When provided, `permitted_teams` is filtered to only teams whose year matches.
- [ ] **AC-3**: When no `year` param is provided, the current calendar year is used. If no teams have data for the current year, the most recent year with data is used as fallback.
- [ ] **AC-4**: A native `<select>` dropdown appears right-aligned in the team selector row, showing available years in descending order. The active year is selected. The dropdown is hidden when only one year has data.
- [ ] **AC-5**: Selecting a different year reloads the page with `?year=YYYY` (no `team_id` carried forward -- the route defaults to the first permitted team for the new year).
- [ ] **AC-6**: The `year` parameter propagates through ALL internal links per epic Technical Notes TN-5: bottom nav bar, team selector pills, game list row links, opponent list row links, player name links in stat tables, and back-links from detail pages.
- [ ] **AC-7**: The detail pages (`/dashboard/opponents/{id}`, `/dashboard/games/{game_id}`, `/dashboard/players/{player_id}`) pass the `year` query parameter through to their template context so that back-links and internal links on those pages preserve the year. These pages do not filter their own data by year (they show a specific item by ID).
- [ ] **AC-8**: The `season_id` for stat queries is derived from the active team's available seasons (existing `get_available_seasons()`). The `season_id` param remains accepted for backward compatibility but `year` takes precedence when both are present.
- [ ] **AC-9**: Tests cover: the new DB function (returns correct year mapping, handles empty teams), route year filtering (default year, explicit year, no-data fallback), and year propagation in template context.

## Technical Approach
Add a DB function that queries `player_season_batting`/`player_season_pitching` UNION joined to `seasons` to build the team→year mapping. In each dashboard route, call this function early, resolve the active year, filter permitted_teams by year, then proceed with existing logic. Add the year dropdown to the team selector area (either in `_team_selector.html` or as a sibling element in each template). Update `base.html` query string builder to include `year`. Propagate `year` through all internal links per TN-5. See epic Technical Notes TN-1 through TN-5.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-133-02

## Files to Create or Modify
- `src/api/db.py` (modify -- add team-year-map function)
- `src/api/routes/dashboard.py` (modify -- add `year` param handling to all routes including game_detail and player_profile)
- `src/api/templates/base.html` (modify -- add `year` to bottom nav query string builder)
- `src/api/templates/dashboard/_team_selector.html` or new `_year_selector.html` partial (modify or create -- add year dropdown, propagate `year` in team pill links)
- `src/api/templates/dashboard/team_stats.html` (modify -- include year selector, add `year` to player name links)
- `src/api/templates/dashboard/team_pitching.html` (modify -- include year selector, add `year` to player name links)
- `src/api/templates/dashboard/game_list.html` (modify -- include year selector, add `year` to game row links)
- `src/api/templates/dashboard/opponent_list.html` (modify -- include year selector, add `year` to opponent row links)
- `src/api/templates/dashboard/game_detail.html` (modify -- add `year` to back-links and player links)
- `src/api/templates/dashboard/opponent_detail.html` (modify -- add `year` to back-links and player links)
- `src/api/templates/dashboard/player_profile.html` (modify -- add `year` to back-link)
- `tests/` (new or modified test files)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-133-02**: Working year dropdown that coexists with the legacy season selector. E-133-02 removes the legacy selector and any dead code.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The year dropdown uses a plain `<select>` with `onchange` form submission -- no JavaScript framework needed.
- During this story, the legacy season selector may still appear below the team selector. That's acceptable; E-133-02 removes it.
- UXD recommends: label "Year:" in `text-xs text-gray-500`, select styled `text-sm border border-gray-300 rounded px-2 py-1 bg-white`.
