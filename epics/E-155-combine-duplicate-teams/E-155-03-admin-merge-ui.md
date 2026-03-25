# E-155-03: Admin Merge UI

## Epic
[E-155: Combine Duplicate Teams](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin team list will display a "Potential Duplicates" banner when duplicate teams are detected, and a dedicated merge page will allow the admin to preview and execute a team merge with full confirmation.

## Context
This is the user-facing layer that connects the merge core logic (E-155-01) and duplicate detection (E-155-02) to the admin interface. The admin workflow: see banner on team list → click to review a duplicate group → pick canonical team → see preview of what will change → confirm → merge executes → redirect back to team list with success message. The admin team list already exists at `/admin/teams` (see `src/api/routes/admin.py` and `src/api/templates/admin/teams.html`).

## Acceptance Criteria
- [ ] **AC-1**: The admin team list (`/admin/teams`) displays a "Potential Duplicates" banner above the team table when `find_duplicate_teams()` returns non-empty results. Each duplicate group shows the team names, count of teams in the group, and a "Resolve" link. The Resolve link passes all team IDs in the group (e.g., `team_ids=X,Y,Z` for a 3-team group).
- [ ] **AC-2**: `GET /admin/teams/merge?team_ids=X,Y[,Z,...]` renders a merge page. When 2 team IDs are provided, the page shows both teams side-by-side. When 3+ team IDs are provided, the page lists all teams in the group and the admin selects any 2 for pairwise merge (after merge, remaining duplicates still appear in the banner). Each team shows key details (name, gc_uuid, public_id, game count, has_stats, membership_type, season_year, last_synced). Radio buttons let the admin pick which team is canonical. On initial load, the page shows the team comparison and direction-independent data (conflict counts are symmetric). When the admin selects a canonical team and submits the selection (or the page defaults to the team with `has_stats=true` or higher game count), the page reloads via GET with `canonical_id` in the query params, showing the full directional preview (identifier gap-fill, self-referencing rows to be removed). Preview data comes from `preview_merge()` and includes: blocking issues (if any, disable the merge button), conflict counts per table, games to be reassigned, games between the two teams (per TN-3 warning check #5), whether the duplicate has `our_team_id` entries in `opponent_links` (per TN-3 warning check #4 -- signals it was treated as a member team), and identifier gap-fill status.
- [ ] **AC-3**: `POST /admin/teams/merge` with `canonical_id` and `duplicate_id` form fields executes the merge via `merge_teams()`. On success, redirects to `/admin/teams` with a success message ("Merged [duplicate name] into [canonical name]. Stats will update on next sync.") and a "Sync Now" form-POST button that triggers `/admin/teams/{canonical_id}/sync`. On blocking validation failure, redirects back to the merge page with an error message.
- [ ] **AC-4**: The merge POST endpoint includes CSRF protection (hidden `csrf_token` field, validated by the existing CSRF middleware).
- [ ] **AC-5**: If `preview_merge()` returns any blocking issues, the "Confirm Merge" button is disabled and the blocking reasons are displayed in a red warning box. The admin cannot submit the form.
- [ ] **AC-6**: The merge page URL supports being linked from the duplicates banner (the "Resolve" link passes the team IDs as query parameters).

## Technical Approach
Add three new route handlers in `src/api/routes/admin.py`: the GET merge page, the POST merge action, and modification to the existing GET `/admin/teams` handler to call `find_duplicate_teams()` and pass results to the template. Create a new template `src/api/templates/admin/merge_teams.html` for the merge page. The duplicates banner is added to the existing `teams.html` template. All database calls go through `run_in_threadpool` per the existing pattern in admin.py.

## Dependencies
- **Blocked by**: E-155-01, E-155-02
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` (modify -- add merge routes, modify teams list route)
- `src/api/templates/admin/teams.html` (modify -- add duplicates banner)
- `src/api/templates/admin/merge_teams.html` (create)
- `tests/test_admin_merge.py` (create)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Follow existing admin UI patterns: Tailwind CSS classes, same nav structure, form actions with CSRF.
- The merge page should make it visually clear which team has more data (game count, `has_stats` indicator, whether it has gc_uuid/public_id) to guide the admin toward picking the right canonical team.
- Error handling: if `team_ids` query param is missing, non-integer, contains fewer than 2 IDs, or references non-existent teams, redirect to `/admin/teams` with an error message.
- **Preview update pattern**: Use server-side reload (GET with updated query params), consistent with the existing admin UI pattern (no JavaScript). When the admin selects canonical and clicks "Preview Merge", the page reloads with `canonical_id` added to the URL, and the full directional preview is rendered server-side. This avoids introducing JS to the admin UI.
- Future enhancement: a "Combine with another team" link on team edit pages could also link to the merge page. Not an AC for this story.
