# E-100-04: Admin UI — Team List, Division, INTEGER URLs

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin team management page will display all teams in a flat table with program, division, and membership columns. All admin team routes will use INTEGER `id` path parameters instead of TEXT `team_id`. The `is_owned` references in admin routes will be replaced with `membership_type`, and `level` references will be replaced with `classification` displayed as "Division."

## Context
The vision pivot established team-and-season as the primary lens, with programs as lightweight organizational metadata. The admin team list replaces the current two-section layout ("Lincoln Program" / "Tracked Opponents") with a flat team-first table — no program-grouped accordion. With the INTEGER PK schema (E-100-01) and the data layer migration (E-100-02), admin routes must use INTEGER team IDs in URLs and pass INTEGER values to db.py functions. This story combines the admin UI update with the INTEGER URL migration because both modify the same files.

## Acceptance Criteria
- [ ] **AC-1**: `GET /admin/teams` displays all teams in a flat table. Columns: team name, program (from programs join, or blank if unassigned), division (classification), membership badge (filled green dot "Member" / hollow gray dot "Tracked"), active/inactive status, opponent count (from team_opponents), edit link.
- [ ] **AC-2**: All admin team routes use INTEGER `{id}` path parameters: `GET /admin/teams/{id}/edit`, `POST /admin/teams/{id}/edit`, `POST /admin/teams/{id}/toggle-active`, `POST /admin/teams/{id}/discover-opponents`. No TEXT `{team_id}` path parameters remain.
- [ ] **AC-3**: `GET /admin/teams/{id}/edit` includes: name field (editable), program dropdown (existing programs, with empty/none option), division dropdown (optgroup: HS group with Varsity/JV/Freshman/Reserve, USSSA group with 8U-14U), active/inactive toggle. Membership type is displayed but not editable.
- [ ] **AC-4**: `POST /admin/teams/{id}/edit` saves program_id and classification to the teams table using INTEGER `id` for the WHERE clause.
- [ ] **AC-5**: All `is_owned` references in `src/api/routes/admin.py` are replaced with `membership_type`. All `level` references in admin routes and templates are replaced with `classification` (displayed as "Division").
- [ ] **AC-6**: Opponent count per team links to the opponents page filtered by that team.
- [ ] **AC-7**: Template links use INTEGER `id` (e.g., `url_for('edit_team', id=team.id)`).
- [ ] **AC-8**: Tests verify: (a) team list renders flat table with program/division/membership columns, (b) edit page saves program_id and classification, (c) membership badges render based on membership_type, (d) all routes use INTEGER id parameters.

## Technical Approach
Refer to the epic Technical Notes "Admin UI Design (Team-First, Revised)" section. The team list is a flat HTML table — no accordion, no JS required. The data layer (db.py, auth.py) was updated in E-100-02 to use INTEGER team references — admin routes now call those functions with integer values. This story does NOT modify `src/api/routes/dashboard.py` or dashboard templates (E-100-05 handles those).

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
- `tests/test_admin.py`
- `tests/test_admin_teams.py`
- `tests/test_admin_opponents.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-100-06**: Admin routes use INTEGER `id`, program dropdown on edit page, division optgroup and membership display patterns established. The two-phase add-team flow builds on these.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Team list query: `SELECT t.*, p.name as program_name FROM teams t LEFT JOIN programs p ON t.program_id = p.program_id ORDER BY t.name`.
- The opponent count per team uses the `team_opponents` junction table.
- The `/admin/opponents` page itself is unchanged — only links to it from the team list are updated.
- Program creation sub-page (`/admin/programs/new`) is deferred — not part of this story. Programs are created by the operator outside the team add/edit flow for now.
