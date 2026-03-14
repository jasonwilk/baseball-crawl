# E-100-04: Admin UI — Team List + Add-Team Flow + INTEGER URLs

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin team management page will display all teams in a flat table with program, division, and membership columns. All admin team routes will use INTEGER `id` path parameters. The `is_owned` and `level` references are replaced with `membership_type` and `classification`. A two-phase add-team flow (URL input -> confirm page with gc_uuid discovery and operator-selected membership) replaces the current single-step form. This is a merged story combining the team list/edit UI with the add-team flow — both touch the same files (admin.py, admin templates).

## Context
The vision pivot established team-and-season as the primary lens. The admin team list replaces the current two-section layout ("Lincoln Program" / "Tracked Opponents") with a flat team-first table. The two-phase add-team flow resolves the team and discovers gc_uuid via the reverse bridge; the operator explicitly selects membership_type (default: tracked). With the INTEGER PK schema (E-100-01) and data layer migration (E-100-02), admin routes use INTEGER team IDs throughout.

## Acceptance Criteria

### Team List and Edit
- [ ] **AC-1**: `GET /admin/teams` displays all teams in a flat table. Columns: team name, program (from programs join, or blank), division (classification), membership badge (filled green "Member" / hollow gray "Tracked"), active/inactive, opponent count (from opponent_links WHERE our_team_id = teams.id), edit link.
- [ ] **AC-2**: All admin team routes use INTEGER `{id}` path parameters: `GET /admin/teams/{id}/edit`, `POST /admin/teams/{id}/edit`, `POST /admin/teams/{id}/toggle-active`, `POST /admin/teams/{id}/discover-opponents`.
- [ ] **AC-3**: `GET /admin/teams/{id}/edit` includes: name field, program dropdown (existing programs + empty option), division dropdown (optgroup: HS with Varsity/JV/Freshman/Reserve, USSSA with 8U-14U, Other with legion), active toggle. Membership type is editable (radio button) — correction path for misclassification.
- [ ] **AC-4**: `POST /admin/teams/{id}/edit` saves name, program_id, classification, and membership_type using INTEGER `id` WHERE clause.
- [ ] **AC-5**: All `is_owned` references in admin routes replaced with `membership_type`. All `level` references replaced with `classification` (displayed as "Division").
- [ ] **AC-6**: Opponent count per team (from opponent_links) links to the opponents page filtered by that team.
- [ ] **AC-7**: Template links use INTEGER `id` (e.g., `url_for('edit_team', id=team.id)`).

### Two-Phase Add-Team Flow
- [ ] **AC-8**: Add-team form on `GET /admin/teams` is a single field (GC URL or public_id) and a submit button. No "team type" radio buttons.
- [ ] **AC-9**: `POST /admin/teams` resolves the team from the URL/public_id, discovers gc_uuid via reverse bridge (success = store UUID, 403 = NULL), and redirects to a confirm page. Errors shown on Phase 1 form.
- [ ] **AC-10**: `GET /admin/teams/confirm` displays resolved team info: team name, gc_uuid status (informational), membership radio (member/tracked, default: tracked), program dropdown (pre-selected if name matches), division dropdown (pre-selected if keywords match).
- [ ] **AC-11**: `POST /admin/teams/confirm` creates the team row with INTEGER PK auto-assigned, operator-selected `membership_type`, `gc_uuid` (UUID if bridge succeeded, NULL otherwise), `public_id`, optional `program_id` and `classification`. Redirects to team list.
- [ ] **AC-12**: gc_uuid discovery: reverse bridge success = gc_uuid stored; `BridgeForbiddenError` = gc_uuid NULL. Membership_type is operator-selected (not bridge-derived). Default is 'tracked'.
- [ ] **AC-13**: Division inference from team name: keywords like "Varsity", "JV", "Freshman", "Reserve", age-group patterns (e.g., "14U") pre-select the division dropdown.
- [ ] **AC-14**: Program pre-selection: existing program name as substring of GC team name (case-insensitive, longest match wins). Defaults to no program if no match.
- [ ] **AC-15**: Duplicate detection: if team already exists (duplicate `public_id` or `gc_uuid`), confirm page shows an error instead of creating a duplicate.

### User-Team Assignment
- [ ] **AC-16**: User management functions in admin.py (`_get_available_teams`, `_get_user_team_ids`, `_create_user`, `_update_user`, create/edit user route handlers) use INTEGER team references (`teams.id`) instead of TEXT `team_id`. Team checkbox values in `edit_user.html` and `users.html` use `team.id` (INTEGER). `user_team_access.team_id` column references are updated to work with INTEGER FK to `teams(id)`.

### Tests
- [ ] **AC-17**: Tests verify: (a) flat team list with correct columns, (b) edit page saves name, program_id, classification, and membership_type, (c) membership badges render correctly, (d) INTEGER id in routes, (e) two-phase add-team flow end-to-end, (f) bridge success -> gc_uuid stored + default tracked, bridge 403 -> gc_uuid NULL + default tracked, (g) duplicate detection, (h) division inference, (i) program pre-selection, (j) team created without program when no match, (k) operator can override membership to 'member' on confirm page, (l) membership editable on edit page, (m) membership_type change persisted on edit POST, (n) user-team assignment works with INTEGER team IDs.
- [ ] **AC-18**: All admin test suites pass: `tests/test_admin.py`, `tests/test_admin_teams.py`, `tests/test_admin_opponents.py`.

## Technical Approach
Refer to the epic Technical Notes "Admin UI Design" and "Membership Assignment (Bridge-Informed)" sections. The team list is a flat HTML table. The data layer (db.py, auth.py) was updated in E-100-02. The existing `url_parser.py` and `team_resolver.py` modules handle URL parsing and GC resolution. The old `_resolve_team_ids()` function is incompatible with INTEGER PK — write a new resolution function returning `(gc_uuid: str | None, public_id: str)`. Membership_type is not returned by the resolution function — it is operator-selected on the confirm page. Confirm page passes resolved info via query parameters between Phase 1 POST and Phase 2 GET. SHOULD: consider re-verifying the bridge on Phase 2 POST (one additional API call) to guard against stale query params — cheap insurance against TOCTOU between Phase 1 and Phase 2.

## Dependencies
- **Blocked by**: E-100-02 (needs INTEGER-aware db.py/auth.py)
- **Blocks**: E-100-06

## Files to Create or Modify
- `src/api/routes/admin.py`
- `src/api/templates/admin/teams.html`
- `src/api/templates/admin/edit_team.html`
- `src/api/templates/admin/confirm_team.html` (CREATE)
- `src/api/templates/admin/edit_user.html` (team checkboxes use team_id)
- `src/api/templates/admin/users.html` (if team references exist)
- `src/api/templates/admin/opponents.html` (team_id references in links)
- `tests/test_admin.py`
- `tests/test_admin_teams.py`
- `tests/test_admin_opponents.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- No api-scout consultation required — reverse bridge and URL resolution are established patterns from E-042/E-094. `url_parser.py`, `team_resolver.py`, and `bridge.py` already exist and are well-tested. This story reuses those modules.
- Team list query: `SELECT t.*, p.name as program_name FROM teams t LEFT JOIN programs p ON t.program_id = p.program_id ORDER BY t.name`.
- Opponent count uses `opponent_links` table (team_opponents is created empty in E-100; populated by future resolver enhancement).
- `/admin/opponents` page itself is unchanged — only links from team list updated.
- Program creation sub-page deferred. Programs created outside the add-team flow.
- The confirm page should handle GC API unreachable — show a generic error on Phase 1.
- `_resolve_team_ids()` and its caller (the old add-team POST handler) are replaced by the new two-phase flow.
