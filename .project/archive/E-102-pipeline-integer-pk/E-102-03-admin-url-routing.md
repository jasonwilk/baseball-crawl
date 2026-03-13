# E-102-03: Admin URL Routing — TEXT to INTEGER Team IDs

## Epic
[E-102: Pipeline INTEGER PK Migration](epic.md)

## Status
`TODO`

## Description
After this story is complete, all admin URL routes that reference teams will use INTEGER IDs (e.g., `/admin/teams/42/edit`) instead of TEXT team_ids. Route parameter types change from `str` to `int`. All admin DB queries will use `teams.id` (INTEGER) for lookups instead of `team_id` (TEXT).

## Context
E-100-03 updates the admin UI for programs, team list, and division — but continues using the existing URL parameter patterns. With INTEGER PKs, admin routes should use the integer `id` for team references, which is more natural for URL routing (shorter, no URL encoding concerns) and aligns with the DB schema.

## Acceptance Criteria
- [ ] **AC-1**: All admin team routes use `{id:int}` path parameters instead of `{team_id}` (e.g., `/admin/teams/{id}/edit`, `/admin/teams/{id}/delete`).
- [ ] **AC-2**: Admin DB queries use `WHERE id = ?` (INTEGER) instead of `WHERE team_id = ?` (TEXT) for team lookups.
- [ ] **AC-3**: Template links to team pages use the INTEGER `id` (e.g., `url_for('edit_team', id=team.id)`).
- [ ] **AC-4**: Dashboard routes that reference teams (if any) are updated to use INTEGER `id`.
- [ ] **AC-5**: All existing tests pass. Tests that construct admin URLs with TEXT team_ids are updated.

## Technical Approach
This is a find-and-replace across admin route handlers and templates. The key change: route parameters and DB queries shift from TEXT to INTEGER. The `teams.id` column is the PK, so all lookups are by primary key — no index changes needed.

## Dependencies
- **Blocked by**: E-102-01 (needs INTEGER PK awareness in the codebase)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py`
- `src/api/routes/dashboard.py` (if team references exist)
- `src/api/templates/admin/teams.html`
- `src/api/templates/admin/edit_team.html`
- `src/api/templates/dashboard/` (if team links exist)
- Test files for admin routes (updates)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
