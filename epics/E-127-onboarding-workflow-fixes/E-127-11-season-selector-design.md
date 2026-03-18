# E-127-11: Season Selector UX Design

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, there will be a UX specification for how the dashboard handles season selection -- including auto-detection of the most recent season with data for the selected team, a season dropdown/selector UI, and season context persistence across tab navigation (Batting/Pitching/Games/Opponents).

## Context
The dashboard currently falls back to `{current_year}-spring-hs` when no `season_id` query parameter is provided. This fails for teams with data in other seasons (e.g., `2025-spring-hs`, `2025-summer`): the page shows "No stats available" with no way to discover which seasons have data. The bottom nav links (Games, Opponents, etc.) also drop `season_id` from URLs, losing season context when navigating between tabs.

Two bugs drive this story:
1. **No season auto-detection**: A team with data only in `2025-spring-hs` shows empty when the default is `2026-spring-hs`. There is no query to find which seasons have data for the team.
2. **Season context lost on navigation**: The bottom nav bar links (e.g., `/dashboard/games`) do not carry `season_id`, so navigating between Batting/Pitching/Games/Opponents resets to the default season.

The dashboard routes all already accept `?season_id=` as a query parameter (`src/api/routes/dashboard.py`), so the backend plumbing exists -- the gap is in the UI and the default-selection logic.

## Acceptance Criteria
- [ ] **AC-1**: A design spec defines the auto-detection behavior: how the dashboard determines the most recent season with data for the selected team when no `season_id` is explicitly provided.
- [ ] **AC-2**: A design spec defines the season selector UI element -- where it appears, how it looks, what information it shows (season name, data availability indicators).
- [ ] **AC-3**: A design spec defines how season context persists across tab navigation (Batting/Pitching/Games/Opponents) -- specifically, how `season_id` is carried through links and the team selector.
- [ ] **AC-4**: The design accounts for edge cases: teams with no data in any season, teams with data in multiple seasons, and the team selector changing to a team with different available seasons.
- [ ] **AC-5**: The design artifact is a text-based spec (not a mockup tool) placed at `epics/E-127-onboarding-workflow-fixes/season-selector-design.md`.
- [ ] **AC-6**: Season labels are human-readable (e.g., "Spring 2025" or "Spring 2025 (HS)"), not raw backend IDs like `2025-spring-hs`. Coaches must instantly recognize what they're looking at. (MUST HAVE per coaching review.)
- [ ] **AC-7**: A data freshness indicator is specified: when the displayed season is from a prior year (not the current calendar year), a visible notice appears (yellow info bar) telling the user they're viewing older data. The design includes the indicator's **message copy**, which must name the season being viewed and explain that newer-season data hasn't been loaded yet (e.g., *"Showing Spring 2025 data -- no 2026 season data has been loaded for this team yet."*). The copy must be actionable for the operator (knows to run a crawl) and non-alarming for coaching staff. (MUST HAVE per coaching review.)
- [ ] **AC-8**: For seasons with thin data (especially opponents), the design specifies showing a game count indicator (e.g., "Spring 2026 (3 games)"). For opponent views, the label should distinguish scouted games from total games played (e.g., "Spring 2026 (5 games scouted)") so coaches know the sample is partial. The design must specify the data requirement: the backend query needs to return a game count per season, not just distinct season IDs. (SHOULD HAVE per coaching review.)
- [ ] **AC-9**: The design explicitly states that the season selector placement must work for both own-team and opponent views, without embedding assumptions about page content ordering (e.g., batting-first). (Future-proofing note per coaching review.)

## Technical Approach
Study the current dashboard templates (`src/api/templates/dashboard/`) and routes (`src/api/routes/dashboard.py`) to understand the existing team selector pattern and navigation structure. Design a season selector that follows the same patterns. Consider whether season detection should be a DB query (e.g., `SELECT DISTINCT season_id FROM player_season_batting WHERE team_id = ?`) or driven by the seasons table.

Key files to study: `src/api/routes/dashboard.py` (season fallback logic at lines 100-102, 234-235, 343-344, 520-521), `src/api/templates/base.html` (bottom nav links), `src/api/templates/dashboard/` (team selector macro, tab navigation).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-127-12

## Files to Create or Modify
- `epics/E-127-onboarding-workflow-fixes/season-selector-design.md` -- design spec artifact

## Agent Hint
ux-designer

## Handoff Context
- **Produces for E-127-12**: Season selector design spec defining auto-detection logic, UI element, and navigation persistence pattern. E-127-12 implements this spec.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Design spec reviewed and covers all ACs
- [ ] Edge cases documented
