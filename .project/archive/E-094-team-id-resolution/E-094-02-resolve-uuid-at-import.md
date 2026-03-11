# E-094-02: Resolve UUID at Team Import Time

## Epic
[E-094: Fix Team ID Resolution in Import and Crawl Pipeline](epic.md)

## Status
`DONE`

## Description
After this story is complete, the admin team import route (`POST /admin/teams`) will store the correct identifier in each database column: UUID as `team_id` for owned teams (resolved via the reverse bridge API) and public_id slug as `team_id` for non-owned teams. The import path will handle both UUID and public_id inputs, resolving the counterpart identifier as needed.

## Context
Currently `add_team()` in `admin.py` calls `parse_team_url()` to get a `public_id`, then passes it as both `team_id` and `public_id` to `_insert_team()`. This means `team_id` contains a slug instead of a UUID, breaking all authenticated crawler endpoints. The fix requires calling the reverse bridge API (`GET /teams/public/{public_id}/id`) at import time for owned teams to resolve the UUID.

The reverse bridge endpoint is documented at `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-public-public_id-id.md`. Key constraint: it returns 403 for teams the user does not belong to (only works for owned teams).

## Acceptance Criteria
- [ ] **AC-1**: Given an owned team added via public_id slug input, the reverse bridge API is called, and `team_id` is stored as the resolved UUID while `public_id` stores the slug.
- [ ] **AC-2**: Given an owned team added via UUID input, the UUID is stored as `team_id`. The public_id is resolved via the forward bridge (`GET /teams/{uuid}/public-team-profile-id`). The team profile is still fetched via public API for name/metadata.
- [ ] **AC-3**: Given a non-owned (tracked) team added via public_id slug, no reverse bridge call is made. `team_id` and `public_id` both store the slug (no UUID available for non-owned teams, and none needed).
- [ ] **AC-3.5**: Given a non-owned (tracked) team added via UUID input, the import fails with a clear error message explaining that non-owned teams require a public_id or GameChanger URL, not a UUID (there is no API path to resolve a non-owned UUID to a public_id).
- [ ] **AC-4**: Given an owned team where the reverse bridge returns 403, the import fails with a clear error message explaining that the team cannot be found on the user's account (the user may have selected "owned" for a team they are not a member of). Note: the 403 response body is a bare string `"Forbidden"` (not JSON) -- error handling must use `response.text`.
- [ ] **AC-5**: The duplicate-check logic (`_team_id_exists`) works correctly when `team_id` is a UUID (owned) or public_id (non-owned). A team with UUID `team_id` and `public_id` slug must not allow re-adding via the same public_id.
- [ ] **AC-6**: The placeholder upgrade path (`_upgrade_placeholder_team`) stores the correct `team_id` (UUID for owned, public_id for non-owned).
- [ ] **AC-7**: All existing `test_admin_teams.py` tests pass (updated as needed). New tests cover: owned team with UUID resolution, non-owned team without UUID resolution, owned team with 403 from reverse bridge, UUID input for owned team.
- [ ] **AC-8**: The `GameChangerClient` usage for the reverse bridge call handles auth errors gracefully. Expired tokens should raise `CredentialExpiredError` (from `src.gamechanger.exceptions`) with a user-friendly message, not an unhandled crash.

## Technical Approach
The `add_team()` route needs to branch on two dimensions: the input type (UUID vs. public_id, from E-094-01) and the team type (owned vs. tracked).

For the reverse bridge call, a `GameChangerClient` instance needs to be created within the import flow. `GameChangerClient` handles auth automatically via `TokenManager`. The client definition is at `src/gamechanger/client.py`.

The resolve step could live in `team_resolver.py` (extending it with an authenticated resolution function) or in `admin.py` directly. Either approach is acceptable -- the implementer should choose based on reusability and testability.

The duplicate check currently tests `_team_id_exists(public_id)`. After the fix, owned teams will have UUID as `team_id`, so the duplicate check must test both the `team_id` column (for UUID match) and the `public_id` column (for slug match). The `idx_teams_public_id` unique partial index (migration 005) provides a DB-level safety net but produces cryptic errors -- the app-level check should catch duplicates first with a clear error message.

Consider extracting bridge API calls (reverse + forward) to a separate module (e.g., `src/gamechanger/bridge.py`) to keep `add_team()` under the 50-line function limit. The admin.py file is already ~1,300 lines; aggressive helper extraction is the lever.

Key reference files:
- `/workspaces/baseball-crawl/src/api/routes/admin.py` -- `add_team()`, `_insert_team()`, `_upgrade_placeholder_team()`
- `/workspaces/baseball-crawl/src/gamechanger/team_resolver.py` -- `resolve_team()`
- `/workspaces/baseball-crawl/src/gamechanger/client.py` -- `GameChangerClient`
- `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-public-public_id-id.md` -- reverse bridge docs
- `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-team_id-public-team-profile-id.md` -- forward bridge docs

## Dependencies
- **Blocked by**: E-094-01 (needs the structured return type from `parse_team_url()`)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` -- update `add_team()`, `_insert_team()`, `_upgrade_placeholder_team()`, duplicate-check logic
- `src/gamechanger/bridge.py` (new, recommended) -- reverse and forward bridge API call helpers
- `src/gamechanger/team_resolver.py` -- optionally add authenticated resolution function(s)
- `tests/test_admin_teams.py` -- update and add tests for UUID resolution paths

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `_insert_team` docstring currently says "equals public_id for URL-added teams" -- this must be updated to reflect the new behavior.
- The `_upgrade_placeholder_team` docstring says the new_team_id parameter is "The resolved public_id (used as the new team_id)" -- same fix needed.
- Tests should mock the reverse bridge API call, not make real network calls.
