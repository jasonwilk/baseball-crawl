# E-100-06: Admin UI — Two-Phase Add-Team Flow with Auto-Detect

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, adding a team via the admin UI will follow a two-phase flow: Phase 1 (URL input) resolves the team from GameChanger, Phase 2 (confirm page) displays the resolved team with auto-detected membership status, pre-populated program and division, and lets the operator confirm or adjust before saving. Membership detection uses the existing reverse bridge endpoint (403 = tracked, success = member). The current single-step add-team form is replaced.

## Context
The current add-team form at `/admin/teams` requires the operator to manually declare "owned" or "tracked" before seeing what team was found — UXD identified this as the core UX problem. The two-phase flow eliminates manual declaration: the system resolves the team, auto-detects membership via the reverse bridge, and presents a confirm page with smart defaults. This story depends on E-100-03 (membership_type in pipeline code) and E-100-04 (programs and division in admin UI) because the confirm page uses the program dropdown, division optgroup, and membership display patterns from those stories.

## Acceptance Criteria
- [ ] **AC-1**: `GET /admin/teams` add-team form is simplified to a single field (GC URL or public_id) and a submit button. No "team type" radio buttons or pre-declarations.
- [ ] **AC-2**: `POST /admin/teams` (the add-team submission) resolves the team from the URL/public_id, detects membership via the reverse bridge, and redirects to a confirm page. If URL parsing or GC resolution fails, an error message is shown on the add-team form (Phase 1) — the user does NOT proceed to Phase 2.
- [ ] **AC-3**: `GET /admin/teams/confirm` (new route) displays the resolved team information: team name (from GC), auto-detected membership status (displayed, not editable), program dropdown (pre-selected if team name matches an existing program, with "＋ Create new program" option), and division dropdown (pre-selected if inferred from team name keywords).
- [ ] **AC-4**: `POST /admin/teams/confirm` creates the team row with: `id` (INTEGER, auto-assigned), `name`, `membership_type`, `program_id` (from dropdown), `classification` (from division dropdown), `public_id`, `gc_uuid` (UUID if member, NULL if tracked), `source='gamechanger'`, `is_active=1`. Redirects to the team list on success.
- [ ] **AC-5**: Membership auto-detect works correctly: the reverse bridge call (`resolve_public_id_to_uuid`) returning a UUID means member (gc_uuid stored); the call raising `BridgeForbiddenError` means tracked (gc_uuid=NULL). No `/me/teams` API call is made.
- [ ] **AC-6**: Division inference from team name: if the GC team name contains "Varsity", "JV", "Freshman", "Reserve", or an age-group pattern (e.g., "14U", "10U"), the division dropdown is pre-selected accordingly. If no match, the dropdown defaults to "-- select --".
- [ ] **AC-7**: Program pre-selection: if an existing program's `name` appears as a substring of the GC team name (case-insensitive), that program is pre-selected. Longest match wins. If no match, defaults to "-- none, or assign --".
- [ ] **AC-8**: The "＋ Create new program" flow from the confirm page routes to `/admin/programs/new?return_team=<public_id>` and redirects back to `/admin/teams/confirm?public_id=<public_id>&program_id=<new_id>` with the new program pre-selected.
- [ ] **AC-9**: If the team already exists in the database (duplicate `public_id` or `gc_uuid`), the confirm page shows an informative error instead of creating a duplicate row.
- [ ] **AC-10**: Tests verify: (a) URL parsing to public_id, (b) bridge success → member detection, (c) bridge 403 → tracked detection, (d) confirm page renders with correct pre-selections, (e) POST confirm creates team row with correct values, (f) duplicate team detection, (g) division inference from team name keywords.

## Technical Approach
Refer to the epic Technical Notes "Membership Auto-Detect (Bridge-Based)" and "Admin UI Design" sections. The confirm page needs resolved team info passed via query parameters between Phase 1 POST and Phase 2 GET (e.g., `?public_id=X&name=Y&membership=member&uuid=Z`). The existing `url_parser.py` and `team_resolver.py` modules handle URL parsing and GC resolution. The `_resolve_team_ids()` function in admin.py already calls the reverse bridge — refactor into the new flow rather than duplicating.

## Dependencies
- **Blocked by**: E-100-03 (membership_type must be standard in pipeline code), E-100-04 (program dropdown and division optgroup must exist)
- **Blocks**: E-100-07

## Files to Create or Modify
- `src/api/routes/admin.py` (modify add-team routes, add confirm routes)
- `src/api/templates/admin/teams.html` (simplify add-team form)
- `src/api/templates/admin/confirm_team.html` (CREATE)
- `tests/test_admin_teams.py` (new tests for add-team flow)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The confirm page should handle GC API unreachable (network error) — show a generic error on Phase 1, don't proceed to Phase 2.
- With the clean schema rewrite (E-100-01), the INSERT uses INTEGER PK — `id` is auto-assigned, `gc_uuid` and `public_id` stored in their respective columns.
