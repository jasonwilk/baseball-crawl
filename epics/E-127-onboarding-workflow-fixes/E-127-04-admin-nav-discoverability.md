# E-127-04: Admin Nav Discoverability

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin UI will be discoverable from the main dashboard via a visible "Admin" link in the top navigation bar. Admin pages will suppress the bottom coaching nav to avoid confusing context mixing. The empty-state "no team assignments" message will link dev-mode users to `/admin/teams`.

## Context
UXD identified the core reason the operator bypassed the admin UI during the 2026-03-18 session: there is no link to `/admin` anywhere in the main navigation or dashboard. The top nav in `base.html` shows only "LSB Baseball". The bottom fixed nav shows Batting/Pitching/Games/Opponents and renders on ALL pages including admin pages, creating confusing context. The admin templates already have their own sub-nav (Users/Teams/Opponents) but it's only visible after you navigate to an admin page directly. The fixes are defined in Technical Notes TN-4.

## Acceptance Criteria
- [ ] **AC-1**: The top navigation bar in `base.html` includes an "Admin" link pointing to `/admin/teams` (the team list is the most useful admin landing page).
- [ ] **AC-2**: On admin pages (`/admin/*`), the bottom coaching nav (Batting/Pitching/Games/Opponents) is suppressed. Admin routes pass `is_admin_page=True` in template context; all other routes omit it (Jinja2 treats undefined as falsy, so the bottom nav renders by default).
- [ ] **AC-3**: The dashboard empty-state message ("You have no team assignments") includes a link to `/admin/teams` when running in dev mode (`DEV_USER_EMAIL` is set), with text guiding the user to add teams.
- [ ] **AC-4**: The "Admin" link in the top nav is placed on the right side of the nav bar (grouped with or immediately before the logout/user area), styled `text-blue-200 hover:text-white` (subdued, matching the logout button weight) within the existing blue-900 nav bar.
- [ ] **AC-5**: Existing admin sub-nav (Users/Teams/Opponents tabs) continues to function correctly.

## Technical Approach
The changes span `base.html` (add admin link to top nav, conditionally suppress bottom nav on admin pages) and the dashboard template (improve empty-state message). Admin pages can be detected via a template variable (e.g., `is_admin_page`) set in admin route handlers, or via URL prefix checking in the template.

Key files to study: `src/api/templates/base.html` (nav structure), `src/api/templates/admin/teams.html` (admin sub-nav pattern), dashboard template with the empty-state message.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/base.html` -- add Admin link to top nav, conditionally suppress bottom coaching nav
- `src/api/routes/admin.py` -- pass `is_admin_page=True` in template context (if using template variable approach)
- Dashboard template file(s) -- improve empty-state message with admin link for dev mode
- `tests/test_admin_routes.py` -- verify admin link presence, bottom nav suppression, and dev-mode empty-state link to `/admin/teams`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
