# E-153-03: Schedule Landing Page and Navigation Restructure

## Epic
[E-153: Team-Centric Coaching Dashboard](epic.md)

## Status
`DONE`

## Description
After this story is complete, the coaching dashboard landing page (`/dashboard/`) shows the team's full season schedule (upcoming and past games) in chronological order. The bottom navigation has 3 tabs (Schedule | Batting | Pitching). Each schedule row links to opponent scouting (upcoming games) or box score (completed games). Coaches can see at a glance which opponents have been scouted and how many days until the next game.

## Context
The current `/dashboard/` landing shows batting stats, which doesn't match the coaching mental model. Expert consultation unanimously recommended the schedule as the primary landing. This story combines the schedule view and navigation restructure because they are tightly coupled -- a schedule page without nav is unreachable, and nav pointing to a nonexistent page is broken. The UX design spec from E-153-01 provides wireframes and component specs. The schedule loader from E-153-02 ensures upcoming games exist in the database.

## Acceptance Criteria
- [ ] **AC-1**: `GET /dashboard/` renders the schedule view (not batting stats). The schedule shows all games for the active team and season in chronological order (date ascending), with upcoming games visually distinguished from completed games per the UX design spec (`/.project/research/E-153-ux-design-spec.md`).
- [ ] **AC-2**: Each upcoming game row displays: date, days-until-game countdown, opponent name (linked to scouting detail), home/away indicator, and a scouted/unscouted badge indicating whether opponent stat data exists. The nearest upcoming game has visual emphasis per Technical Notes TN-5.
- [ ] **AC-3**: Each completed game row displays: date, opponent name (linked to scouting detail), home/away indicator, score (linked to box score detail at `/dashboard/games/{game_id}`), and W/L indicator.
- [ ] **AC-4**: The bottom navigation bar in `base.html` has exactly 3 tabs: Schedule (links to `/dashboard/`), Batting (links to `/dashboard/batting`), Pitching (links to `/dashboard/pitching`). Active tab highlighting works correctly on all three pages.
- [ ] **AC-5**: The existing batting stats page is accessible at `/dashboard/batting` (moved from `/dashboard/`). The old `/dashboard/` URL now serves the schedule, not batting stats.
- [ ] **AC-6**: The team selector and year selector continue to work on the schedule page, preserving the existing parameter resolution behavior (team_id, year, season_id query params).
- [ ] **AC-7**: Existing routes `/dashboard/games`, `/dashboard/games/{game_id}`, `/dashboard/opponents`, `/dashboard/opponents/{id}`, and `/dashboard/players/{id}` continue to function (accessible via direct URL and internal links). They are removed from bottom nav but not deleted.
- [ ] **AC-8**: The scouted/unscouted badge per opponent is determined by checking whether `player_season_batting` OR `player_season_pitching` has any rows for that opponent's team_id in the current season, per Technical Notes TN-3. This matches the "full stats" definition used by E-153-04 (opponent detail page).
- [ ] **AC-9**: Empty states handled: (a) when the user has no permitted teams, a "no team assignments" message is displayed (consistent with existing dashboard pages), (b) when no games exist for the team/season, a message is displayed (e.g., "No schedule data yet. Run a data sync to load your team's schedule.").
- [ ] **AC-10**: Games with `home_away` unknown (null at load time) display gracefully -- either "TBD" or omit the H/A indicator rather than showing incorrect home/away.
- [ ] **AC-11**: Tests verify: (a) schedule view renders with a mix of completed and upcoming games sorted date ASC, (b) bottom nav contains exactly 3 tabs with labels "Schedule", "Batting", "Pitching" and correct href values, (c) scouted badge logic correctly distinguishes opponents with stat data from those without, (d) `/dashboard/batting` serves the batting stats page previously at `/dashboard/`, (e) internal links in batting stats template navigate to `/dashboard/batting`, not `/dashboard/`.

## Technical Approach
Read the UX design spec at `/.project/research/E-153-ux-design-spec.md` for wireframes and component inventory. Adapt the existing `get_team_games()` query in `src/api/db.py` (or create a new query) per Technical Notes TN-3 -- add `g.status` to SELECT, change to `ORDER BY g.game_date ASC`, add the CTE for scouting status. The days-until calculation can be done in Python (comparing game_date to today). Create a new schedule template. Update `base.html` bottom nav per TN-4. Move the batting stats handler to a new URL path.

## Dependencies
- **Blocked by**: E-153-01 (UX design spec), E-153-02 (schedule loader -- upcoming games in DB)
- **Blocks**: E-153-04 (opponent detail redesign -- modifies shared templates)

## Files to Create or Modify
- `src/api/routes/dashboard.py` (modify: move batting from `/dashboard/` to `/dashboard/batting`, add schedule route at `/dashboard/`)
- `src/api/db.py` (modify: new schedule query or adapt `get_team_games()`)
- `src/api/templates/dashboard/schedule.html` (create: new schedule template)
- `src/api/templates/base.html` (modify: 3-tab bottom nav)
- `src/api/templates/dashboard/team_stats.html` (modify: audit and update any hardcoded `/dashboard` links that now need to point to `/dashboard/batting`)
- `src/api/templates/dashboard/player_profile.html` (modify: "Back to Team Stats" links at lines 20/24 hardcode `/dashboard` -- must become `/dashboard/batting`)
- `tests/` (new/modified tests for schedule view and navigation)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `_resolve_year_and_team()` helper and `_pick_season_for_year()` helper from existing routes should be reused for the schedule page's team/year resolution.
- The existing `/dashboard/games` game log route can remain as-is (still useful for a full game history view). It's just no longer in the nav.
- Consider whether `/dashboard/opponents` should redirect to `/dashboard/` or remain as a standalone page. The simplest approach: keep the route working, remove from nav.
