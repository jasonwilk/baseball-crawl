# E-133-02: Remove Legacy Season Selector

## Epic
[E-133: Year Selector Dropdown](epic.md)

## Status
`TODO`

## Description
After this story is complete, the legacy season pill-button selector (`_season_selector.html`) will be removed from all dashboard templates. The year dropdown from E-133-01 is the sole time-navigation mechanism. Dead code related to the old season selector (template macro, unused template variables, stale warning banner) is cleaned up.

## Context
E-133-01 adds the year dropdown while keeping the legacy season selector in place for safety. This story removes the old selector and any code that only existed to support it. The `season_id` query parameter remains functional for direct URL access but is no longer exposed in the UI.

## Acceptance Criteria
- [ ] **AC-1**: The `_season_selector.html` template partial is deleted.
- [ ] **AC-2**: All dashboard templates no longer import or call the `season_selector` macro.
- [ ] **AC-3**: The `is_current_season` warning banner ("Showing X data -- no Y season data...") in `team_stats.html` is removed entirely, per epic Technical Notes TN-6. No replacement banner is needed -- the year dropdown makes past-year viewing an explicit user choice.
- [ ] **AC-4**: Template context variables that only existed for the season selector (`available_seasons`, `is_current_season`, `current_year`) are removed from route handlers if no longer consumed by any template. Variables still used elsewhere (e.g., by the year dropdown logic) are retained.
- [ ] **AC-5**: The `format_season_display` Jinja2 filter registration is removed if no template uses it. If the player profile page or other pages still reference it, it is left in place.
- [ ] **AC-6**: All existing tests pass after cleanup. No functional regressions.
- [ ] **AC-7**: The `season_id` query parameter continues to work for direct URL access (backward compatibility).

## Technical Approach
Delete the `_season_selector.html` file. Grep for all imports/calls of the `season_selector` macro across templates and remove them. Audit route handlers for template context variables that are no longer consumed by any template and remove the dead assignments. Check if `format_season_display` is still used anywhere; if not, remove the filter registration and function. Run tests to verify no regressions.

## Dependencies
- **Blocked by**: E-133-01
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/dashboard/_season_selector.html` (delete)
- `src/api/templates/dashboard/team_stats.html` (modify -- remove season_selector import/call, remove warning banner if stale)
- `src/api/templates/dashboard/team_pitching.html` (modify -- remove season_selector import/call)
- `src/api/templates/dashboard/game_list.html` (modify -- remove season_selector import/call)
- `src/api/templates/dashboard/opponent_list.html` (modify -- remove season_selector import/call)
- `src/api/routes/dashboard.py` (modify -- remove unused template context variables)
- `src/api/helpers.py` (potentially -- remove `format_season_display` if unused)
- `tests/` (modify -- update or remove tests for season selector, warning banner, and `format_season_display` if removed)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This is a cleanup story. It should be small and straightforward given that E-133-01 already has the year dropdown working.
- The `get_available_seasons()` DB function should NOT be removed -- it is still used to resolve `season_id` from a team (per TN-4).
