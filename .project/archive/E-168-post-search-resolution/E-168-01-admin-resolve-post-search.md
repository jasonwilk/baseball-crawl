# E-168-01: Switch Admin Resolve Search to POST /search

## Epic
[E-168: Switch Opponent Resolution to POST /search](epic.md)

## Status
`DONE`

## Description
After this story is complete, the admin opponent resolve workflow will search for teams using `POST /search` instead of `GET /search/opponent-import`. Search results will display correctly with data from the verified response schema, and clicking "Select" will pass both `public_id` and `gc_uuid` through the confirm flow so `resolve_team()` receives a valid `public_id` slug and succeeds without the UUID-mismatch fallback.

## Context
The current `_gc_search_teams` helper calls `GET /search/opponent-import`, whose response body was never captured -- the schema is entirely inferred. The confirm flow passes the result's `id` (likely a UUID) to `resolve_team(public_id)` which 404s, triggering a fragile fallback. `POST /search` has a live-verified schema (2026-03-27) returning both `id` (UUID) and `public_id` (slug) per result.

## Acceptance Criteria
- [ ] **AC-1**: Given the admin resolve page for an unresolved opponent, when the page loads or the user submits a search query, then the backend calls `POST /search` (not `GET /search/opponent-import`) with the query in the request body per TN-1.
- [ ] **AC-2**: Given POST /search returns results, when `_gc_search_teams` returns, then each result is a flat dict with the normalized shape per TN-3 (keys: `name`, `gc_uuid`, `public_id`, `city`, `state`, `season_year`, `season_name`, `sport`, `num_players`, `staff`).
- [ ] **AC-3**: Given search results are rendered in the template, when the user views the results list, then each result displays the team name, location (city/state), and season year from the normalized fields.
- [ ] **AC-4**: Given a user clicks "Select" on a search result, when the confirm page loads, then the URL passes `public_id` as the `confirm` parameter and `gc_uuid` as an additional query parameter (e.g., `?confirm=<public_id>&gc_uuid=<uuid>`).
- [ ] **AC-5**: Given a user clicks "Select" on a search result, when the confirm page renders, then `confirm_id` is a `public_id` slug (not a UUID), matching the format expected by `resolve_team()`.
- [ ] **AC-6**: Given the user confirms the resolution (POST handler), when the form is submitted, then both `public_id` (from `confirm_id` form field) and `gc_uuid` (from a new hidden form field) are passed to `ensure_team_row()`, and the opponent link is updated with `resolution_method='search'`.
- [ ] **AC-7**: Given POST /search returns an empty `hits` array, when the search results page renders, then the "no results" message displays correctly.
- [ ] **AC-8**: Given POST /search returns an API error, when the search fails, then the error message displays and the "Paste URL manually" fallback link remains available.
- [ ] **AC-9**: `GameChangerClient` has a **new** method (distinct from the existing `post()` which returns `None` for 204 endpoints and has live callers) that sends an authenticated POST request with a JSON body, optional query parameters, a caller-specified Content-Type, and returns the parsed JSON response. The existing `post()` method is unchanged. The new method's error contract matches the existing `get()` method: 401 retry (token refresh) then `CredentialExpiredError` on persistent 401, `ForbiddenError` on 403, `RateLimitError` on 429, `GameChangerAPIError` on 5xx.
- [ ] **AC-10**: The search form's state, city, and year filter inputs are removed from the template (POST /search only supports name-based search; non-functional filters would confuse the admin user).
- [ ] **AC-11**: Tests cover the new client method, the normalized response shape, the confirm flow with both `public_id` and `gc_uuid`, and the error/empty cases.

## Technical Approach
**Client extension:** The existing `GameChangerClient.post()` is a 204-only fire-and-forget method that cannot send JSON bodies or parse responses, and has live callers (e.g., follow/unfollow in `opponent_resolver.py`). This story adds a **new** method (e.g., `post_json()`) that accepts a JSON body dict, optional query parameters, a custom Content-Type header, and returns parsed JSON. The existing `post()` method is left unchanged. E-168-02 depends on the new method.

**Search helper:** The `_gc_search_teams` helper in `src/api/routes/admin.py` switches from `client.get("/search/opponent-import", ...)` to the new client method with the Content-Type and body per TN-1. The helper normalizes the `hits[].result` objects into flat dicts per TN-3 before returning.

**Template:** Updates field references to match the normalized dict keys. The "Select" link changes from `?confirm={{ team.id }}` to `?confirm={{ team.public_id }}&gc_uuid={{ team.gc_uuid }}`. The state/city/year filter inputs are removed from the search form since POST /search only supports name-based search (server-side filtering beyond `name` is unconfirmed). Leaving non-functional filter UI would confuse the admin user.

**Confirm flow:** The confirm GET handler (`resolve_opponent_page`) reads `gc_uuid` from query params and passes it to the template as a hidden form field. The confirm POST handler (`resolve_opponent_confirm`) reads `gc_uuid` from the form and passes it to `ensure_team_row()` along with the `public_id`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-168-02, E-168-03

## Files to Create or Modify
- `src/gamechanger/client.py` (modify: extend with JSON-body POST method for POST /search)
- `src/api/routes/admin.py` (modify `_gc_search_teams`, `resolve_opponent_page`, `resolve_opponent_confirm`)
- `src/api/templates/admin/opponent_resolve.html` (modify field references, confirm link, hidden form field, remove state/city/year filter inputs)
- `tests/test_admin_resolve.py` or equivalent (create or modify tests for the search + confirm flow)
- `tests/test_client.py` or equivalent (add tests for the new client method)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `_SEARCH_ACCEPT` constant (`application/vnd.gc.com.none+json; version=0.0.0`) used for the GET endpoint is replaced with the POST Content-Type per TN-6.
- The `year`, `state`, `city` params on `_gc_search_teams` should be removed (POST /search doesn't support them). The search form filter inputs are also removed from the template.
- `resolve_team()` in `src/gamechanger/team_resolver.py` is NOT modified -- it already works correctly when given a real `public_id`.
- The new client method is a prerequisite for E-168-02 (auto-resolver fallback). Design it as a general-purpose JSON POST method, not search-specific.
- Model the new method's 401 retry logic on the existing `get()` method, not the existing `post()` method (which has no retry logic).
