# E-150-01: Cascade Delete with Confirmation Page

## Epic
[E-150: Team Lifecycle Management](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin UI will support full deletion of any team -- including all related data -- through a two-step flow: a GET confirmation page that shows exactly what will be deleted, followed by a POST that performs the cascade. The current zero-data-only restriction is replaced with a deliberate confirmation workflow that surfaces row counts, game-sharing implications, and shared opponent warnings.

## Context
The current delete route (`POST /admin/teams/{id}/delete`) only works for teams with zero data rows. `_check_team_has_data` blocks any team that has games, player stats, scouting runs, or spray charts. `_delete_team_cascade` only removes junction/access rows. The confirmation is a browser `window.confirm()` dialog. This story replaces all of that with a server-rendered confirmation page and a full 4-phase cascade delete.

## Acceptance Criteria
- [ ] **AC-1**: Given a team with related data (games, player stats, scouting runs), when the admin clicks "Delete" on the team list page, then a GET confirmation page loads showing the team name, membership type, active status, row counts per table, and total row count across all tables (per Technical Notes TN-4).
- [ ] **AC-2**: Given the confirmation page, when the team has affected games (home_team_id=T OR away_team_id=T), then the page displays the count of affected games and the count of distinct opponent teams whose per-game stats will also be removed as a consequence of game deletion.
- [ ] **AC-3**: Given a tracked team that appears in `team_opponents` or `opponent_links` linked from at least one member team (per Technical Notes TN-2), when the confirmation page loads, then a shared-opponent warning is displayed identifying which member teams reference this opponent.
- [ ] **AC-4**: Given a member team with tracked opponents linked only from this team via `team_opponents`, when the confirmation page loads, then an informational notice lists opponents that will become orphaned (linked from no member team after deletion).
- [ ] **AC-5**: Given the admin confirms deletion on the confirmation page, when the POST executes, then all related rows are deleted in the correct 4-phase order (per Technical Notes TN-1) within a single transaction, and the team row is removed.
- [ ] **AC-6**: Given the admin cancels on the confirmation page (e.g., clicks a "Cancel" link), then no data is modified and the admin returns to the team list page.
- [ ] **AC-7**: Given a team with zero related data, when the admin clicks "Delete", then the confirmation page still loads (showing zero counts) and the delete proceeds normally through the same flow.
- [ ] **AC-8**: The existing deactivation requirement is removed -- teams can be deleted whether active or inactive. The confirmation page's explicitness replaces the deactivation guard as the safety mechanism.
- [ ] **AC-9**: Tests verify: (a) cascade deletion order removes all FK-dependent rows for a team with data across all affected tables, (b) shared-opponent detection, (c) orphaned-opponent detection, (d) GET confirmation route returns correct row counts and template context for a team with data, and (e) GET confirmation route returns zero counts for a team with no data.

## Technical Approach
The existing `_check_team_has_data` and `_delete_team_cascade` functions in `src/api/routes/admin.py` need to be reworked. The check function becomes the data-gathering function for the confirmation page (returning counts instead of a boolean). The cascade function is extended to include the 4-phase deletion order from Technical Notes TN-1. A new GET route serves the confirmation page; the existing POST route is updated to perform the full cascade and the `is_active` guard on the existing POST handler must be removed (AC-8). A new template (`confirm_delete.html`) renders the confirmation page following existing admin template patterns. The delete trigger in `teams.html` changes from a form POST to a link to the GET confirmation page.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` -- rework delete route (GET confirmation + POST cascade), extend `_delete_team_cascade`, replace `_check_team_has_data` with count-gathering function
- `src/api/templates/admin/confirm_delete.html` -- new confirmation page template
- `src/api/templates/admin/teams.html` -- change delete form to link to confirmation page
- `tests/test_admin_delete_cascade.py` -- new test file for cascade delete logic
- `tests/test_admin_teams.py` -- update existing `TestDeleteTeam` tests that assert old behavior (zero-data guard, deactivation required, delete button hidden for active teams)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- DE confirmed: no migration needed. Application-code ordering is the established pattern and avoids SQLite ALTER TABLE limitations.
- The `seasons` table does NOT reference teams -- it references programs. Excluded from cascade.
- `spray_charts` has nullable team_id and game_id FKs. Phase 1 catches spray_charts rows linked via game_id; Phase 3 catches any remaining spray_charts rows where team_id=T but game_id is NULL (both phases are needed -- see TN-1).
