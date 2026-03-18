# E-127-12: Season Selector Implementation

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the dashboard will auto-detect the most recent season with data for the selected team, display a season selector UI, and persist season context across all tab navigation (Batting/Pitching/Games/Opponents). Users will no longer need to manually construct URLs with `&season_id=` to view data from non-default seasons.

## Context
The dashboard defaults to `{current_year}-spring-hs` when no `season_id` is provided. Teams with data in other seasons (e.g., `2025-spring-hs`, `2025-summer`) show "No stats available." The bottom nav links drop `season_id` entirely. The UX design for the season selector is specified in E-127-11's design artifact -- this story implements that design.

All dashboard routes already accept `?season_id=` as a query parameter. The implementation gap is:
1. **Default logic**: Replace the hardcoded `f"{datetime.date.today().year}-spring-hs"` fallback with a query that finds the most recent season with data for the selected team.
2. **Season selector UI**: Add a dropdown/selector per the E-127-11 design spec.
3. **Navigation persistence**: Ensure all dashboard links (bottom nav, team selector, back links) carry `season_id`.

## Acceptance Criteria
- [ ] **AC-1**: When no `season_id` query parameter is provided, the dashboard auto-detects the most recent season with data for the selected team (not a hardcoded year/type).
- [ ] **AC-2**: A season selector UI element is rendered on the four main dashboard tab pages (Batting, Pitching, Games list, Opponents list), showing available seasons for the selected team, per the E-127-11 design spec. The selector is suppressed (not rendered) when only one season has data for the team. Detail pages (game detail, opponent detail, player profile) do NOT display the season selector.
- [ ] **AC-3**: All navigation links (bottom nav tabs, back links in detail pages like `← Games` and `← Opponents`, game detail links) include the current `season_id` as a query parameter. Team selector links should OMIT `season_id` to trigger auto-detection for the new team (per E-127-11 design spec).
- [ ] **AC-4**: Changing the selected team updates the season selector to show seasons available for the new team, and auto-selects the most recent season with data.
- [ ] **AC-5**: Edge case: a team with no data in any season shows an appropriate empty state (not a broken page).
- [ ] **AC-6**: Tests verify: (a) season auto-detection returns the most recent season with data, (b) `available_seasons` and `season_id` are present in template context for all four main tab routes, (c) navigation link generation includes `season_id`, (d) empty-state behavior for teams with no data, (e) the `season_display` Jinja2 filter is unit tested for all known season ID patterns including those without a classification suffix (e.g., `2025-summer`) and non-HS suffixes (e.g., `2025-spring-legion`, `2025-spring-reserve`), (f) season selector is not rendered when only one season has data.
- [ ] **AC-7**: A data freshness indicator (yellow info bar per E-127-11 design spec) is displayed between the selectors and page h1 when the displayed season is from a prior year (`is_current_season = False`). Not shown when the active season year matches the current calendar year, even if stats are empty.

## Technical Approach
Read the E-127-11 design artifact at `epics/E-127-onboarding-workflow-fixes/season-selector-design.md` for the UX specification. The implementation touches the dashboard routes (season default logic) and templates (season selector, navigation links).

The season auto-detection requires a DB query sourcing from **data tables** (not the `seasons` reference table, which lists all defined seasons regardless of whether the team has data). Per DE review, the correct pattern:
```sql
SELECT DISTINCT season_id FROM player_season_batting WHERE team_id = ?
UNION
SELECT DISTINCT season_id FROM player_season_pitching WHERE team_id = ?
ORDER BY season_id DESC
```
UNION (not UNION ALL) deduplicates. Lexicographic DESC ordering works for the current `{year}-{type}-{level}` slug format.

**Data freshness indicator**: Backend computes `is_current_season = (active_season_year == datetime.date.today().year)` and passes it to all four main tab templates. Templates show a yellow info bar (existing `bg-yellow-50 border border-yellow-200` pattern) when `not is_current_season`, between the selectors and page h1.

**New Jinja2 filter**: `season_display` strips all known classification suffixes (`-hs`, `-jv`, `-freshman`, `-reserve`, `-legion`), capitalizes the season word, and outputs season-first format (e.g., `2026-spring-hs` → "Spring 2026", `2025-summer` → "Summer 2025", `2025-spring-legion` → "Spring 2025"). Season-first matches how coaches talk ("Spring 2025", not "2025 Spring"). Must handle IDs without suffixes and unknown suffixes gracefully (strip anything after the second hyphen-delimited segment).

**New macro**: `_season_selector.html` following the pill-button pattern of `_team_selector.html`. Suppress when only one season has data.

**Team selector behavior**: Team selector links should OMIT `season_id` (let auto-detection run for the new team). All other links (bottom nav, back links, game detail) carry `season_id`.

Key files: `src/api/routes/dashboard.py` (season fallback at lines 100-102, 234-235, 343-344, 520-521), `src/api/db.py` (new `get_available_seasons(team_id)` query), `src/api/templates/base.html` (bottom nav links -- requires `active_team_id` and `season_id` in context for ALL dashboard routes), `src/api/templates/dashboard/*.html` (season selector macro, team selector macro signature update, back links). Consult the E-127-11 design artifact for the full UX spec.

## Dependencies
- **Blocked by**: E-127-11 (season selector design), E-127-04 (admin nav -- both touch `base.html` and dashboard templates)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/dashboard.py` -- replace hardcoded season fallback with auto-detection
- `src/api/db.py` -- add query for available seasons per team
- `src/api/templates/base.html` -- season_id in bottom nav links
- `src/api/templates/dashboard/*.html` -- season selector UI, season_id in all links
- `tests/test_dashboard_routes.py` -- season auto-detection, navigation, empty-state tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
