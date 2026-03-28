# E-173-03: Unified Resolve Page (Find on GC)

## Epic
[E-173: Fix Opponent Scouting Workflow End-to-End](epic.md)

## Status
`DONE`

## Description
After this story is complete, the separate "Resolve" (search-based) and "Connect" (URL-paste) flows are merged into a single admin page titled "Find [opponent] on GameChanger." Search is the primary action with URL paste as a fallback below a divider. Search result cards display enriched fields (season year badge, player count, staff names) per the absorbed E-171 scope. Both paths lead to the same confirm step and auto-scout trigger.

## Context
Currently, the admin UI has two separate entry points for linking an opponent to a GameChanger team: the "Resolve" flow (search-based, using `opponent_resolve.html`) and the "Connect" flow (URL-paste, using `opponent_connect.html` + `opponent_connect_confirm.html`). This creates confusion about which to use. Merging into one page with search primary and URL-paste as fallback matches the UXD proposal and eliminates the decision point.

Additionally, E-171-resolve-search-enrichment identified that search result cards underutilize available data -- season year is tiny gray text, and player count/staff names are not shown at all despite being in the API response.

## Acceptance Criteria
- [ ] **AC-1**: A single route serves the unified resolve page at `GET /admin/opponents/{link_id}/resolve`. The page title is "Find [opponent_name] on GameChanger" with the member team name shown below.
- [ ] **AC-2**: The page layout has three sections per TN-4: search form (top), "or" divider, URL paste form (bottom), with "No match -- skip" as a de-emphasized link at the very bottom.
- [ ] **AC-3**: Search result cards display: team name (bold), season year (prominent badge -- `bg-blue-100 text-blue-800` or similar, NOT `text-xs text-gray-400`), city/state (secondary line), player count (e.g., "14 players"), and staff names (smallest text, comma-separated). All fields sourced from the existing `_gc_search_teams()` normalized dict.
- [ ] **AC-4**: Selecting a search result navigates to the existing confirm step (currently served as a mode of the resolve route via query parameter), which then triggers the resolution + auto-scout (per E-173-01 and E-173-02).
- [ ] **AC-5**: Submitting a URL in the paste section POSTs to a handler that parses the URL via `parse_team_url()`, extracts the `public_id`, and redirects to the existing confirm step (served as a mode of the resolve route via query parameter) with the `public_id` as a query parameter. The confirm step renders the same team info card as the search confirm flow and submits to the **resolve POST endpoint** (not the connect POST). Both URL-paste and search paths use the same confirm template and the same POST handler.
- [ ] **AC-6**: The old "Connect" GET routes (`GET /admin/opponents/{link_id}/connect` and `GET /admin/opponents/{link_id}/connect/confirm`) return HTTP 303 redirects to the new unified resolve page. The `POST /admin/opponents/{link_id}/connect` endpoint is retained for backward compatibility (e.g., bookmarked forms) but is NOT the primary path -- new URL-paste confirmations submit to the resolve POST per AC-5.
- [ ] **AC-7**: The "No match -- skip" link calls the existing skip/hide endpoint (`POST /opponents/{link_id}/skip`).
- [ ] **AC-8**: The old `opponent_connect.html` template is no longer the entry point (the connect route redirects to resolve). The template may be retained for the URL-paste confirm step if needed, or removed if the confirm step is unified.
- [ ] **AC-9**: Tests verify the unified page renders with all three sections and that the old connect URL redirects.

## Technical Approach
The existing `opponent_resolve.html` template already has the search form and result cards. The change is to add the URL-paste section below a divider within the same template, and to enrich the search result cards with the additional fields. The existing `_gc_search_teams()` function already returns `season_year`, `num_players`, and `staff` -- they just need to be rendered. The connect route handlers can redirect to the resolve page rather than serving a separate template. The URL-paste confirm step can reuse the existing connect confirm logic.

## Dependencies
- **Blocked by**: E-173-01 (both paths must call `finalize_opponent_resolution()`), E-173-02 (unified page description references auto-scout trigger; both stories modify `admin.py` and test files)
- **Blocks**: E-173-05 (terminology changes depend on the unified page existing)

## Files to Create or Modify
- `src/api/templates/admin/opponent_resolve.html` -- add URL-paste section, enrich search result cards with season year badge, player count, staff
- `src/api/routes/admin.py` -- modify `connect_opponent_form` to redirect to resolve page; ensure URL-paste submission works from the unified page
- `src/api/templates/admin/opponent_connect.html` -- may be removed or retained for URL confirm step
- `tests/test_admin_resolve.py` -- test unified page renders all sections
- `tests/test_admin_connect.py` -- test redirect from old connect URL

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `opponent_connect_confirm.html` template (used after URL lookup to show team details before confirming) may still be needed as an intermediate step. The unified page shows search results inline, but URL-paste results need a confirm step since the operator hasn't seen the team info yet. Consider whether this can be the same confirm page as the search flow.
- The E-171 search enrichment fields (`season_year` badge, `num_players`, `staff`) are already available in the template context via the `results` list. This is purely a template rendering change for the search cards.
