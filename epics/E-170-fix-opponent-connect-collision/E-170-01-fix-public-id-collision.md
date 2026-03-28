# E-170-01: Fix public_id Collision in save_manual_opponent_link and Harden Confirm Page

## Epic
[E-170: Fix Opponent Connect public_id Collision (500 Error)](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin opponent connect flow will handle the case where a stub team has `public_id=None` but the target `public_id` already belongs to another team row. Instead of crashing with a 500 IntegrityError, the system will merge by repointing `resolved_team_id` to the existing team, surface a flash message to the operator, and warn on the confirm page before submission.

## Context
This is the sole story in E-170. The bug is a missing collision check in `save_manual_opponent_link` (line 1301-1305 of `src/api/db.py`). The `existing_public_id is None` branch blindly UPDATEs without checking if another team row owns the target `public_id`. The adjacent `elif` branch (line 1306-1326) already has the correct collision check pattern. The confirm page's duplicate detection only queries `opponent_links`, not `teams`, so it misses this scenario entirely.

## Acceptance Criteria
- [ ] **AC-1**: Given a stub team with `public_id=None` and another team row that already owns the target `public_id`, when `POST /admin/opponents/{link_id}/connect` is submitted, then the response is a 303 redirect (not a 500 error).
- [ ] **AC-2**: Given the collision scenario in AC-1, when the connect succeeds, then `opponent_links.resolved_team_id` is set to the existing team that owns the `public_id` (not the stub team's id).
- [ ] **AC-3**: Given the collision scenario in AC-1, when the connect succeeds, then the redirect flash message includes the name of the existing team that was merged into (e.g., "Linked [opponent] -- pointed to existing team [name]"). The merge flash message takes priority over any `opponent_links` duplicate warning per Technical Notes "Flash Message Priority".
- [ ] **AC-4**: Given a `public_id` that already exists in the `teams` table, when the confirm page (`GET /admin/opponents/{link_id}/connect/confirm`) loads, then the page displays a warning indicating the team already exists in the database. This warning must be distinct from the existing `opponent_links` duplicate warning per Technical Notes "Confirm Page Hardening" (different message text — e.g., "A team with this URL already exists as [name]" vs the existing "This URL is already linked to [name]").
- [ ] **AC-5**: Given a `public_id` that does NOT collide with any existing team row, when `POST /admin/opponents/{link_id}/connect` is submitted, then the existing behavior is preserved (stub gets the `public_id`, `resolved_team_id` = stub_id, normal success message).
- [ ] **AC-6**: Test coverage for the collision scenario: at least one test where a team row already owns the target `public_id`, the POST succeeds (303), `resolved_team_id` points to the existing team, and the flash message mentions the existing team name.
- [ ] **AC-7**: Test coverage for the confirm page collision warning: at least one test where a team row already owns the target `public_id`, the GET confirm page includes a warning.
- [ ] **AC-8**: All existing tests in `tests/test_admin_opponents.py` continue to pass (no regressions).

## Technical Approach
The collision check pattern already exists in the `elif` branch of `save_manual_opponent_link` (line 1307-1326). The `None` branch needs the same query. When a collision is found, skip the stub UPDATE and repoint `resolved_team_id` to the collision row. The function's return value needs to change to signal merge info to the route handler -- see epic Technical Notes for the return value structure. The route handler builds the flash message from the return value. For the confirm page, add a `teams`-table query alongside the existing `opponent_links` check in `_get_duplicate_name_for_link` or as a parallel check passed to the template.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` -- `save_manual_opponent_link`: add collision check in `None` branch, change return value
- `src/api/routes/admin.py` -- `connect_opponent`: handle merge return value, build flash message; `connect_opponent_confirm` / `_get_duplicate_name_for_link`: add `teams`-table collision check
- `tests/test_admin_opponents.py` -- new tests for collision scenario (POST + GET confirm)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `elif` branch (line 1306-1326) has two sub-paths: when a collision is found (line 1311-1316), it logs a warning and skips the `UPDATE teams`; when no collision exists, it overwrites the stub's `public_id` with a warning log. In both sub-paths, `resolved_team_id` is set to `stub_id` unconditionally (line 1328-1331) — the collision sub-path has the same class of bug as the `None` branch (resolves to wrong team). This story does not change the `elif` branch behavior (different trigger conditions — stub already has a different `public_id`; rarer scenario).
- Orphan stubs (left behind after merge) are harmless name-only rows. No cleanup in this story.
