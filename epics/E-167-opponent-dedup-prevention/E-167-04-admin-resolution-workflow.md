# E-167-04: Admin Opponent Resolution Workflow with GC Search Suggestions

## Epic
[E-167: Opponent Dedup Prevention and Resolution](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin opponents page shows an "Unresolved Opponents" banner, and clicking "Resolve" on an unresolved opponent opens a search-powered suggestion page with GC team matches. The admin can select a match (with duplicate detection at confirm time), refine the search, dismiss as "no match", or fall back to manual URL paste. This replaces the blank "connect opponent" form with a guided resolution workflow.

## Context
~44 tracked teams have no gc_uuid and ~132 have no public_id. The current "Connect" form requires the admin to manually find and paste a GC team URL. The GC search endpoint (`GET /search/opponent-import`) enables smart suggestions -- searching GC's database by name + filters. UXD designed a three-step flow: opponents list (with banner) → suggestion page (auto-search + refine) → confirm page (with duplicate detection). The response schema for the search endpoint is inferred but not captured -- the implementer must verify it. The `is_hidden` column already exists on `opponent_links` and is used for the "No match" skip action (dual-purpose: hides from admin banner AND filters from pipeline).

## Acceptance Criteria
- [ ] **AC-1**: The admin opponents page (`/admin/opponents`) displays an "Unresolved Opponents" banner when the count of opponents with `resolved_team_id IS NULL AND is_hidden = 0` is > 0. The banner shows the count and a "Start resolving" link that navigates to `?filter=unresolved`. A new `unresolved` filter value is added to `src/api/db.py` that matches `resolved_team_id IS NULL AND is_hidden = 0` (distinct from the existing `scoresheet` filter which uses `public_id IS NULL`).
- [ ] **AC-2**: Unresolved opponent rows show a "Resolve" button (renamed from "Connect") that links to `GET /admin/opponents/{link_id}/resolve`.
- [ ] **AC-3**: `GET /admin/opponents/{link_id}/resolve` renders a suggestion page per TN-6. The page auto-searches the GC endpoint with the opponent's name + `sport=baseball` + `year={season_year}` (where `season_year` is the member team's `season_year`, falling back to the current calendar year). Each search result card MUST display the team name at minimum. Additional fields (location, age group, record) are rendered when available in the response. If the response does not include a team name field, the stop-and-report protocol fires (see Notes). Each card has a "Select" button.
- [ ] **AC-4**: The suggestion page includes a "Refine Search" form with name (pre-filled), state, and city fields per TN-6. Submitting reloads the page with refined search results via GET params.
- [ ] **AC-5**: The suggestion page includes a "No match -- skip" button that POSTs to `/admin/opponents/{link_id}/skip`, sets `is_hidden = 1` on the opponent_link row, and redirects to `/admin/opponents?filter=unresolved`.
- [ ] **AC-6**: The suggestion page includes a "Paste URL manually" link that navigates to the existing `/admin/opponents/{link_id}/connect` form.
- [ ] **AC-7a**: Selecting a search result navigates to a confirm page (`GET /admin/opponents/{link_id}/resolve?confirm=<team_gc_id>`) showing the selected GC team's profile. If the team's `public_id` matches an existing row in the `teams` table, a duplicate warning is shown per TN-6 with a link to the merge page.
- [ ] **AC-7b**: The "Confirm connection" button (POST to `/admin/opponents/{link_id}/resolve`) creates/updates the team row via `ensure_team_row()`, sets `resolved_team_id` and `resolution_method = 'search'` on the opponent_link, and redirects to `/admin/opponents?filter=unresolved` with a success message. The POST uses `ensure_team_row()` to handle the race condition where another pipeline run may have created the team row between the GET and POST (see TN-6).
- [ ] **AC-8**: When the GC search returns 0 results, the suggestion page shows "No teams found" with the refine search form and the manual paste and skip options prominently visible.
- [ ] **AC-9**: CSRF protection is applied to all POST endpoints (skip and confirm).
- [ ] **AC-10**: Tests cover the suggestion page (with mocked GC search response), the confirm flow, the skip flow, duplicate detection at confirm time, the unresolved banner count, and the unhide flow.
- [ ] **AC-11**: A new `hidden` filter tab is added to the opponents page showing only `is_hidden = 1` rows. Hidden rows appear ONLY in this tab (the existing All/Full stats/Scoresheet only tabs continue to exclude them). Each hidden row shows an "Unhide" button that POSTs to set `is_hidden = 0`, making the opponent visible in the unresolved banner again. The `get_opponent_link_counts()` function returns a `hidden` count in addition to the existing counts, displayed on the tab badge.
- [ ] **AC-12**: If the GC search API call fails (auth expired, network error, HTTP 500), the suggestion page shows an error message and prominently displays the "Paste URL manually" fallback link. The page does not crash.

## Technical Approach
Add route handlers in `src/api/routes/admin.py`: GET resolve (suggestion page), POST resolve (confirm connection), and POST skip. Create `opponent_resolve.html` template with two modes (`suggestions` and `confirm`) following the existing pattern in `opponent_connect.html`. The GC search call goes through `GameChangerClient` (authenticated endpoint). The confirm step uses `ensure_team_row()` from E-167-01 to create/update the team row, then updates the opponent_link row. For the search endpoint response schema, execute a test call first and adapt the UI to whatever fields are actually returned (see TN-7).

## Dependencies
- **Blocked by**: E-167-01 (needs `ensure_team_row()` for the confirm step)
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` (modify -- add `unresolved` filter value to opponent link query)
- `src/api/routes/admin.py` (modify -- add resolve/skip routes, modify opponents list for banner)
- `src/api/templates/admin/opponent_resolve.html` (create)
- `src/api/templates/admin/opponents.html` (modify -- banner, rename Connect to Resolve, add unresolved filter tab)
- `tests/test_admin_resolve.py` (create)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The search endpoint response schema is inferred but not captured (see TN-7). The implementer MUST execute a test search call to verify the actual response body before building the template. If fields differ from the inferred schema, adapt the card layout to show whatever is actually available. If the response does not include `public_id`, the confirm step writes only `gc_uuid` and sets `resolution_method = 'search'` (see TN-6 public_id contingency).
- The "Resolve" button replaces "Connect" for unresolved rows. Already-resolved rows (with auto/manual/follow-bridge resolution) keep their existing UI.
- Queue-optimized redirect: after resolve or skip, redirect to `?filter=unresolved` so the admin sees the next unresolved opponent immediately.
- The existing `opponent_connect.html` form and route remain as a fallback path. The "Paste URL manually" link on the suggestion page navigates to it.
- For the GC search call, use the existing `GameChangerClient` with the authenticated session. The search endpoint requires gc-token auth. Handle auth failure gracefully per AC-12.
- The "No match" action uses `is_hidden = 1` on the opponent_link row (not a new `resolution_method` value). This reuses the existing `is_hidden` column and has the dual benefit of also suppressing the opponent from pipeline processing (per TN-4). This avoids the COALESCE interaction bug where a `resolution_method = 'no_match'` value would be permanently preserved by the resolver's upsert SQL.
- Hidden opponents (`is_hidden = 1`) are visible ONLY in the new `hidden` filter tab (not in All/Full stats/Scoresheet only). Each hidden row shows a "Hidden" badge and an "Unhide" button. They are excluded from the unresolved banner count. The existing `_opponent_links_where()` in `src/api/db.py` globally excludes `is_hidden = 1` -- the new `hidden` filter must override this (pass `is_hidden = 1` instead of `is_hidden = 0`).
- **Race condition**: Between the admin viewing the suggestion page and clicking "Confirm," another pipeline run may create a row for the same team. The confirm POST uses `ensure_team_row()` (which handles dedup atomically) to prevent double-creation.
- **Search param passthrough**: The refine form submits name, state, and city as GET params. These are passed to the GC search endpoint alongside the fixed `sport=baseball` and `year` params. The auto-search on page load uses the opponent's name as default.
- **Stop-and-report**: If the implementer discovers that the GC search endpoint response schema differs materially from the inferred structure in `docs/api/endpoints/get-search-opponent-import.md` (e.g., no team IDs in results, pagination is required, response is nested differently), stop implementation, update the endpoint doc with actual findings, and report to PM before continuing with the template.
- The confirm step unconditionally sets `resolution_method = 'search'` on the opponent_link row (overwriting any previous value). The admin's explicit action is the most authoritative resolution.
