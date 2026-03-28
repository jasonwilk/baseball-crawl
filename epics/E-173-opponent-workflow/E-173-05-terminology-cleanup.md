# E-173-05: Admin and Dashboard Terminology Cleanup

## Epic
[E-173: Fix Opponent Scouting Workflow End-to-End](epic.md)

## Status
`TODO`

## Description
After this story is complete, all pipeline jargon is replaced with plain English across admin and dashboard templates. The "Discover Opponents" button is removed (discovery is automatic after member sync). Filter pills on the admin opponents page use coaching-friendly labels. Dashboard empty states use clear, non-technical language. The "Tracked" membership badge says "Opponent." The Opponents tab in admin sub-nav shows an unresolved count badge.

## Context
The baseball-coach walkthrough identified terminology issues across 7 templates. "Discover", "Sync", "Scout", "Resolve", "Connect" are pipeline jargon that confuses the admin and is invisible to coaches. This story implements the terminology mapping from TN-5 and the UXD proposal. It depends on E-173-03 (unified resolve page) because button labels reference the new page structure.

## Acceptance Criteria
- [ ] **AC-1**: The "Discover Opponents" button is removed from the team list page (`admin/teams.html`) and its corresponding route handler (`discover_team_opponents` in `admin.py`) is removed. Opponent discovery remains automatic via `run_member_sync` (it already runs the seeder).
- [ ] **AC-2**: Filter pills on the admin opponents page (`admin/opponents.html`) are renamed per TN-5: "All" | "Stats loaded" | "Needs linking" | "Hidden". The old "Full stats" / "Scoresheet only" / "Unresolved" labels are replaced.
- [ ] **AC-3**: Action buttons on the admin opponents page: "Resolve" becomes "Find on GameChanger" (linking to the unified resolve page from E-173-03). "Connect" button is removed (merged into resolve page).
- [ ] **AC-4**: The "Tracked" membership badge is changed to "Opponent" in all admin templates that render it: `admin/teams.html`, `admin/edit_team.html`, `admin/confirm_team.html`, `admin/confirm_delete.html`, and `admin/merge_teams.html`.
- [ ] **AC-5**: Dashboard opponent detail empty states use non-technical language per TN-5: (a) Unlinked state: "Scouting stats aren't available for this team. Only scoresheet data from your games is shown." (b) Linked-but-unscouted state: "Stats are on their way. Check back soon."
- [ ] **AC-6**: The Opponents tab in the admin sub-nav shows an unresolved count badge (e.g., "(3)") when opponents need linking. The badge uses `text-orange-600 font-bold`. The badge disappears when all opponents are resolved or hidden. The count must be available in the template context for ALL admin routes (not just the opponents page), so the badge renders regardless of which admin tab is active. This requires injecting the count via middleware, a Jinja2 context processor, or a shared template-context helper called from every admin route.
- [ ] **AC-7**: The admin opponents page unresolved banner (if present) is reworded to: "N opponents need linking to GameChanger for full stats."
- [ ] **AC-8**: Tests verify that the removed "Discover Opponents" button no longer renders, that new filter pill labels appear, and that the unresolved count badge renders with the correct count.
- [ ] **AC-9**: Per-row status badges in the admin opponents table are replaced with pipeline-aware states: "Needs linking" (`bg-orange-100 text-orange-800`) for unresolved, "Syncing..." (`bg-yellow-100 text-yellow-800`) for `crawl_jobs` with `status = 'running'`, "Stats loaded" (`bg-green-100 text-green-800`) for opponents with season stat data, "Sync failed" (`bg-red-100 text-red-800`) for `crawl_jobs` with `status = 'failed'`, and "Hidden" (`bg-gray-100 text-gray-600`). This requires the same `crawl_jobs` and stat-existence query pattern described in TN-3.
- [ ] **AC-10**: Dashboard opponent list and detail pages replace any remaining pipeline jargon in banners or instructional text with plain English. For example, "Run a data crawl to populate stats" becomes "Stats aren't available yet." No references to "crawl", "sync", "pipeline", "resolver", or "seeder" appear in any dashboard-facing template.

## Technical Approach
This is primarily a template change story. Most changes are string replacements in Jinja2 templates. The unresolved count badge requires a query (count of `opponent_links` rows where `resolved_team_id IS NULL AND is_hidden = 0`). The admin sub-nav is currently copy-pasted across 10 admin templates (no shared partial). Two implementation approaches: (a) extract a shared `admin/_subnav.html` partial and include it from all 10 templates, or (b) update the badge in all 10 templates individually. Option (a) is recommended since AC-6 requires the badge on ALL admin routes. The filter pill backend mapping (query parameter values) may need updating if the URL parameters change, or the old parameter values can be preserved with only the display labels changing.

## Dependencies
- **Blocked by**: E-173-03 (button labels reference the unified resolve page), E-173-04 (both stories modify `src/api/db.py` and `dashboard/opponent_list.html`)
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/admin/teams.html` -- remove "Discover Opponents" button; change "Tracked" badge to "Opponent"
- `src/api/templates/admin/edit_team.html` -- change "Tracked" badge to "Opponent"
- `src/api/templates/admin/confirm_team.html` -- change "Tracked" badge to "Opponent"
- `src/api/templates/admin/confirm_delete.html` -- change "Tracked" badge to "Opponent"
- `src/api/templates/admin/merge_teams.html` -- change "Tracked" badge to "Opponent"
- `src/api/templates/admin/opponents.html` -- rename filter pills, rename action buttons, add unresolved count badge to sub-nav, update banner wording
- `src/api/templates/admin/users.html` -- add unresolved count badge to sub-nav Opponents tab
- `src/api/templates/admin/programs.html` -- add unresolved count badge to sub-nav Opponents tab
- `src/api/templates/admin/edit_user.html` -- add unresolved count badge to sub-nav Opponents tab
- `src/api/templates/admin/opponent_connect.html` -- add unresolved count badge to sub-nav Opponents tab (if template retained)
- `src/api/templates/dashboard/opponent_detail.html` -- update empty state copy for unlinked and linked-unscouted states
- `src/api/templates/dashboard/opponent_list.html` -- replace any pipeline jargon in banners or instructional text
- `src/api/templates/dashboard/team_stats.html` -- replace "Run a data crawl to populate batting stats" with plain English
- `src/api/templates/dashboard/team_pitching.html` -- replace "Run a data crawl to populate pitching stats" with plain English
- `src/api/templates/dashboard/game_list.html` -- replace "Run a data crawl to populate game data" with plain English
- `src/api/templates/dashboard/schedule.html` -- replace "Run a data sync to load your team's schedule" with plain English
- `src/api/routes/admin.py` -- pass unresolved opponent count to template context for the badge
- `src/api/db.py` -- add `get_unresolved_opponent_count()` function (or inline query)
- `tests/test_admin_teams.py` or relevant admin test -- verify "Discover" button removed
- `tests/test_admin_opponents.py` or relevant test -- verify new labels and badge

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The "Tracked" -> "Opponent" badge change should apply everywhere the membership type badge is rendered, not just the team list. Check `admin/edit_team.html` and any other templates that display membership type.
- The filter pill URL parameters can remain as-is (e.g., `?filter=full`, `?filter=scoresheet`) with only the display label changing, to avoid breaking bookmarks or existing links. Alternatively, update both -- the user base is one person (Jason), so backward compatibility is not a concern.
