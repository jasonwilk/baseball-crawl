# E-114-04: Fix Dashboard and Admin Template Stale References

## Epic
[E-114: E-100 Codex Review Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, all templates use the correct user dict fields from the E-100 schema. Six dashboard templates still reference `user.display_name` and `user.is_admin` which no longer exist, and one admin template references `admin_user.display_name` -- Jinja2 silently renders nothing, so admin nav links never appear and user names are blank on these pages.

## Context
E-100 simplified the user model, removing `display_name` and `is_admin` from the user dict. The `dashboard/team_stats.html` template was updated to use `user.email`, but six other dashboard templates and one admin template were missed. Jinja2's undefined-variable tolerance masks the bug -- pages render without errors but with missing content (blank user name, invisible admin links). The admin template (`admin/opponent_connect.html`) uses `admin_user.display_name` where `admin_user` is the same user dict passed from the admin guard.

## Acceptance Criteria
- [ ] **AC-1**: `dashboard/team_pitching.html`, `dashboard/game_list.html`, `dashboard/opponent_list.html`, `dashboard/opponent_detail.html`, `dashboard/player_profile.html`, and `dashboard/game_detail.html` use `user.email` instead of `user.display_name` for user identification display.
- [ ] **AC-2**: All references to `user.is_admin` conditionals are removed from the six dashboard templates listed in AC-1. Admin navigation is handled by the same pattern used in `dashboard/team_stats.html`.
- [ ] **AC-3**: `admin/opponent_connect.html` uses `admin_user.email` instead of `admin_user.display_name`.
- [ ] **AC-4**: A test renders at least one of the fixed dashboard templates with a known user email and asserts the email appears in the rendered HTML. Additionally, a source-level assertion (grep or file read) confirms the template files no longer contain the literal strings `display_name` or `is_admin`.
- [ ] **AC-5**: Existing template and route tests continue to pass.

## Technical Approach
Audit all seven templates for `display_name` and `is_admin` references. For dashboard templates, replace with the pattern already established in `dashboard/team_stats.html` (which was correctly updated during E-100). For the admin template, the pattern is the same but uses the `admin_user` variable name. The fix is mechanical across all files.

Context files to read:
- `/workspaces/baseball-crawl/src/api/templates/dashboard/team_stats.html` (reference -- correct pattern)
- `/workspaces/baseball-crawl/src/api/templates/dashboard/team_pitching.html`
- `/workspaces/baseball-crawl/src/api/templates/dashboard/game_list.html`
- `/workspaces/baseball-crawl/src/api/templates/dashboard/opponent_list.html`
- `/workspaces/baseball-crawl/src/api/templates/dashboard/opponent_detail.html`
- `/workspaces/baseball-crawl/src/api/templates/dashboard/player_profile.html`
- `/workspaces/baseball-crawl/src/api/templates/dashboard/game_detail.html`
- `/workspaces/baseball-crawl/src/api/templates/admin/opponent_connect.html`

## Dependencies
- **Blocked by**: None
- **Blocks**: E-114-05 (shared `tests/test_dashboard.py`)

## Files to Create or Modify
- `src/api/templates/dashboard/team_pitching.html` (modified)
- `src/api/templates/dashboard/game_list.html` (modified)
- `src/api/templates/dashboard/opponent_list.html` (modified)
- `src/api/templates/dashboard/opponent_detail.html` (modified)
- `src/api/templates/dashboard/player_profile.html` (modified)
- `src/api/templates/dashboard/game_detail.html` (modified)
- `src/api/templates/admin/opponent_connect.html` (modified)
- `tests/test_dashboard.py` (modified -- new assertion)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
