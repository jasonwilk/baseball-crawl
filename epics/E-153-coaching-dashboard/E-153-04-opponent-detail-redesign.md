# E-153-04: Opponent Detail Redesign

## Epic
[E-153: Team-Centric Coaching Dashboard](epic.md)

## Status
`TODO`

## Description
After this story is complete, the opponent scouting detail page (`/dashboard/opponents/{opponent_team_id}`) leads with pitching data, shows game count alongside all rate stats, and handles three distinct states gracefully: full stats available, linked but unscouted, and unlinked (name-only). Admin users see a contextual shortcut to the admin linking page for unlinked opponents.

## Context
The current opponent detail page leads with a "Key Players" card (best hitter first), which reflects data availability rather than coaching priority. Coach consultation confirmed the first question is always "Who's on the mound?" The page needs to be reorganized per Technical Notes TN-6 and TN-7. The UX design spec from E-153-01 provides wireframes for all three opponent states.

## Acceptance Criteria
- [ ] **AC-1**: The opponent detail page sections appear in this order: (1) Header with name + record + game count, (2) Pitching card with key pitchers, (3) Team batting summary, (4) Last Meeting card, (5) Full pitching table, (6) Full batting table -- per Technical Notes TN-6.
- [ ] **AC-2**: The pitching card (section 2) shows the top 3 pitchers by innings pitched, displaying ERA, K/9, BB/9, K/BB ratio, and games pitched for each. If `players.throws` is populated, pitcher handedness (L/R) is displayed. This replaces the current "Key Players" card's pitcher section which showed only the single best pitcher.
- [ ] **AC-3**: The team batting summary (section 3) shows team-level aggregate tendencies: OBP, K rate, BB rate, SLG -- computed from the season batting data. This is a compact summary card, not the full sortable table. The team's total game count is displayed alongside the rates (e.g., "Team Batting (12 games)") per Technical Notes TN-7.
- [ ] **AC-4**: Every rate stat display on the page includes the game count alongside it per Technical Notes TN-7 (e.g., "2.10 ERA (8 GP)", ".310 OBP (12 GP)").
- [ ] **AC-5**: When the opponent is **unlinked** (no `opponent_links` row with `resolved_team_id IS NOT NULL` for the active member team's `our_team_id`, AND the opponent `teams` row has `public_id IS NULL`, AND no stat rows in `player_season_batting`/`player_season_pitching`): a yellow info card displays "Stats not available. This opponent hasn't been linked to a GameChanger team yet." If the current user has admin role (determined per Technical Notes TN-6 admin role detection), a "Link this team in Admin" shortcut link appears -- pointing to `/admin/opponents/{link_id}/connect` if an `opponent_links` row exists for this `our_team_id`, or `/admin/opponents` if none exists.
- [ ] **AC-6**: When the opponent is **linked but unscouted** (has an `opponent_links` row with `resolved_team_id IS NOT NULL` for the active member team's `our_team_id`, OR the opponent `teams` row has `public_id IS NOT NULL`, BUT no rows in `player_season_batting`/`player_season_pitching` for this team_id + season_id): a yellow info card displays "This team is linked but stats haven't been loaded yet." The page still shows the opponent name and any game dates.
- [ ] **AC-7**: When the opponent has **full stats** (at least one row in `player_season_batting` or `player_season_pitching` for this team_id + season_id): all sections render with data. No yellow info cards.
- [ ] **AC-8**: The "Back to" link at the top navigates to the schedule page (`/dashboard/`) instead of the opponents list, reflecting the new navigation structure.
- [ ] **AC-9**: Verify that the opponent detail route (`/dashboard/opponents/{opponent_team_id}`) does not return 403 for opponents that exist only as scheduled-game stub teams. After E-153-02 inserts game rows and `team_opponents` rows for stub opponents, the existing authorization checks should already permit access. This AC verifies correctness -- if the auth check unexpectedly excludes stub opponents, fix it.
- [ ] **AC-10**: Tests verify: (a) pitching-first section order renders correctly, (b) unlinked state shows the correct empty-state card, (c) linked-but-unscouted state shows the correct card, (d) admin shortcut link appears only for admin users, (e) stub-team opponents are accessible without 403.

## Technical Approach
Read the UX design spec at `/.project/research/E-153-ux-design-spec.md` for wireframes. Modify the existing opponent detail route handler and template. The route handler already fetches batting and pitching stats via `get_opponent_scouting_report()` -- add a check for empty results to determine the linked-but-unscouted state. For the unlinked state, add a new db helper that takes both `opponent_team_id` AND `our_team_id` (the active member team) and checks whether the opponent has an `opponent_links` row with `resolved_team_id IS NOT NULL` scoped to `our_team_id` (or a `teams` row with `public_id IS NOT NULL`). The `our_team_id` parameter is required because `opponent_links` rows are scoped per member team -- without it, the helper could misclassify based on another member team's link status. Admin role detection: `request.state.user` does NOT contain the user's role directly -- consult the existing `_require_admin()` pattern in `src/api/routes/admin.py` which checks `ADMIN_EMAIL` env var OR queries `users.role`. The team batting summary card computes aggregate rates from the existing batting data (SUM across all players with qualifying AB).

## Dependencies
- **Blocked by**: E-153-01 (UX design spec), E-153-03 (navigation restructure -- shared template changes in base.html)
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/dashboard/opponent_detail.html` (modify: reorder sections, add empty states, add admin shortcut)
- `src/api/routes/dashboard.py` (modify: opponent detail handler -- add state detection, team batting summary data)
- `src/api/db.py` (modify: add helper to check opponent scouting status -- linked/unlinked/scouted)
- `tests/` (new/modified tests for opponent detail states)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The existing `get_opponent_scouting_report()` query returns batting/pitching lists. Empty lists could mean either unlinked or linked-but-unscouted. The route handler needs a separate `opponent_links` query to distinguish these states.
- The pitching card shows top 3 pitchers by innings pitched (most usage = most likely to face), replacing the current single-best-pitcher by K/9.
- K/BB ratio is computed as `so / bb`. When bb = 0, display "--" (not a numeric value).
- Pitcher handedness (`throws` L/R) may be NULL for most players in the current dataset. Display it when available; omit gracefully when NULL.
- The admin shortcut link requires looking up `opponent_links.id` for this opponent. The new db helper should accept both `opponent_team_id` and `our_team_id`, query `opponent_links` scoped to `our_team_id`, and return the `opponent_links` row (if any) alongside the scouting status, providing the `link_id` for the admin URL construction.
