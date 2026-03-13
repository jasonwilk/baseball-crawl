# E-100-04: Admin UI — Programs, Team List, Division, INTEGER URLs

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin team management page will display teams grouped by program in accordion sections with member/tracked badges and division labels. Programs will be manageable through the admin UI (create via sub-page). All admin team routes will use INTEGER `id` path parameters instead of TEXT `team_id`. The `is_owned` references in admin routes will be replaced with `membership_type`, and `level` references will be replaced with `classification` displayed as "Division."

## Context
UXD designed a program-grouped accordion layout replacing the current flat two-section list ("Lincoln Program" / "Tracked Opponents"). With the INTEGER PK schema (E-100-01) and the data layer migration (E-100-02), admin routes must use INTEGER team IDs in URLs and pass INTEGER values to db.py functions. This story combines the admin UI redesign with the INTEGER URL migration because both modify the same files.

## Acceptance Criteria
- [ ] **AC-1**: `GET /admin/teams` displays teams grouped by program in collapsible accordion sections. Each section header shows the program name. Teams show: name, division (classification), membership badge (filled green dot "Member" / hollow gray dot "Tracked"), active/inactive status, edit link. An "Unassigned" section appears for `program_id=NULL` teams.
- [ ] **AC-2**: All admin team routes use INTEGER `{id}` path parameters: `GET /admin/teams/{id}/edit`, `POST /admin/teams/{id}/edit`, `POST /admin/teams/{id}/toggle-active`, `POST /admin/teams/{id}/discover-opponents`. No TEXT `{team_id}` path parameters remain.
- [ ] **AC-3**: `GET /admin/teams/{id}/edit` includes: name field (editable), program dropdown (existing programs + "＋ Create new program"), division dropdown (optgroup: HS group with Varsity/JV/Freshman/Reserve, USSSA group with 8U-14U), active/inactive toggle. Membership type is displayed but not editable.
- [ ] **AC-4**: "＋ Create new program" routes to `GET /admin/programs/new?return_team={id}` — a form with program name and program type (HS/USSSA/Legion). On save, creates the program and redirects back to the edit page with the new program pre-selected.
- [ ] **AC-5**: `POST /admin/teams/{id}/edit` saves program_id and classification to the teams table using INTEGER `id` for the WHERE clause.
- [ ] **AC-6**: All `is_owned` references in `src/api/routes/admin.py` are replaced with `membership_type`. All `level` references in admin routes and templates are replaced with `classification` (displayed as "Division").
- [ ] **AC-7**: The team list header includes a disabled "Import from GC" button (placeholder, no route).
- [ ] **AC-8**: Each program section shows opponent count per team linking to the opponents page filtered by that team.
- [ ] **AC-9**: Template links use INTEGER `id` (e.g., `url_for('edit_team', id=team.id)`).
- [ ] **AC-10**: Tests verify: (a) team list renders program groups, (b) edit page saves program_id and classification, (c) program creation redirects correctly, (d) membership badges render based on membership_type, (e) all routes use INTEGER id parameters.

## Technical Approach
Refer to the epic Technical Notes "Admin UI Design (UXD Consensus)" section. The accordion can use pure HTML `<details>`/`<summary>` elements (no JS). The data layer (db.py, auth.py) was updated in E-100-02 to use INTEGER team references — admin routes now call those functions with integer values. This story does NOT modify `src/api/routes/dashboard.py` or dashboard templates (E-100-05 handles those).

## Dependencies
- **Blocked by**: E-100-02 (needs INTEGER-aware db.py/auth.py)
- **Blocks**: E-100-06

## Files to Create or Modify
- `src/api/routes/admin.py`
- `src/api/templates/admin/teams.html`
- `src/api/templates/admin/edit_team.html`
- `src/api/templates/admin/edit_user.html` (team checkboxes use team_id)
- `src/api/templates/admin/users.html` (if team references exist)
- `src/api/templates/admin/opponents.html` (team_id references in links)
- `src/api/templates/admin/new_program.html` (CREATE)
- `tests/test_admin.py`
- `tests/test_admin_teams.py`
- `tests/test_admin_opponents.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-100-06**: Admin routes use INTEGER `id`, programs CRUD exists, division optgroup and membership display patterns established. The two-phase add-team flow builds on these.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Program-grouped query: `SELECT t.*, p.name as program_name FROM teams t LEFT JOIN programs p ON t.program_id = p.program_id ORDER BY p.name, t.classification`.
- The opponent count per team uses the `team_opponents` junction table.
- The `/admin/opponents` page itself is unchanged — only links to it from the team list are updated.
